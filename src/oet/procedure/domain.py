"""
The oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
import dataclasses
import enum
import importlib.machinery
import logging
import multiprocessing
import signal
import threading
import time
import traceback
import types
import typing
from collections import OrderedDict
from multiprocessing.dummy import Pool

from pubsub import pub

from oet.command import SCAN_ID_GENERATOR
from oet.event import topics

LOGGER = logging.getLogger(__name__)

PROCEDURE_QUEUE_MAX_LENGTH = 10

DEFAULT_SIGTERM_HANDLER = signal.getsignal(signal.SIGTERM)


class ProcedureState(enum.Enum):
    """
    Represents the script execution state.
    """

    CREATED = enum.auto()
    RUNNING = enum.auto()
    COMPLETED = enum.auto()
    STOPPED = enum.auto()
    FAILED = enum.auto()


@dataclasses.dataclass
class ProcedureInput:
    """
    ProcedureInput is a non-functional dataclass holding the arguments passed
    to a script method.
    """

    def __init__(self, *args, **kwargs):
        self.args: tuple = args
        self.kwargs: dict = kwargs

    def __eq__(self, other):
        if not isinstance(other, ProcedureInput):
            return False
        if self.args == other.args and self.kwargs == other.kwargs:
            return True
        return False

    def __repr__(self):
        args = ", ".join((str(a) for a in self.args))
        kwargs = ", ".join(["{!s}={!r}".format(k, v) for k, v in self.kwargs.items()])
        return "<ProcedureInput({})>".format(", ".join((args, kwargs)))


@dataclasses.dataclass
class ProcedureHistory:
    """
    ProcedureHistory is a non-functional dataclass holding execution history of
    a Procedure.

    process_states: records time for each change of ProcedureState (list of
        tuples where tuple contains the ProcedureState and time when state was
        changed to)
    stacktrace: None unless execution_error is True in which case stores
        stacktrace from process
    """

    def __init__(self, process_states=None, stacktrace=None):
        if process_states is None:
            process_states = OrderedDict()
        self.process_states: typing.OrderedDict[ProcedureState, float] = process_states
        self.stacktrace = stacktrace

    def __eq__(self, other):
        if not isinstance(other, ProcedureHistory):
            return False
        if (
            self.process_states == other.process_states
            and self.stacktrace == other.stacktrace
        ):
            return True
        return False

    def __repr__(self):
        p_history = ", ".join(
            ["({!s}, {!r})".format(s, t) for s, t in self.process_states.items()]
        )
        return "<ProcessHistory(process_states=[{}], " "stacktrace={})>".format(
            p_history, self.stacktrace
        )


class Procedure(multiprocessing.Process):
    """
    A Procedure is the OET representation of a Python script, its arguments,
    and its execution state.
    """

    def __init__(
        self,
        script_uri: str,
        *args,
        scan_counter: typing.Optional[multiprocessing.Value] = None,
        procedure_id: typing.Optional[int] = None,
        **kwargs,
    ):
        multiprocessing.Process.__init__(self)
        self.stacktrace_queue = multiprocessing.Queue()
        self.history = ProcedureHistory()
        init_args = ProcedureInput(*args, **kwargs)

        self.id = procedure_id  # pylint:disable=invalid-name
        self.state = None

        self.user_module = ModuleFactory.get_module(script_uri)
        if hasattr(self.user_module, "init"):
            self.user_module.init(*args, **kwargs)

        self.script_uri = script_uri
        self.script_args: typing.Dict[str, ProcedureInput] = dict(
            init=init_args, run=ProcedureInput()
        )
        self.change_state(ProcedureState.CREATED)

        self._scan_counter = scan_counter

    def run(self):
        """
        Run user module script. Called from start() and executed in a child process

        This calls the main() method of the target script.
        """
        # set shared scan ID backing store, if provided
        if self._scan_counter:
            SCAN_ID_GENERATOR.backing = self._scan_counter

        msg_src = threading.current_thread().name
        topic = topics.procedure.lifecycle.stopped

        try:
            args = self.script_args["run"].args
            kwargs = self.script_args["run"].kwargs
            self.user_module.main(*args, **kwargs)

        except Exception as exception:  # pylint: disable=broad-except
            LOGGER.debug(
                "Process terminated unexpectedly. Exception caught: %s", exception
            )
            stacktrace = traceback.format_exc()
            self.stacktrace_queue.put(stacktrace)
            topic = topics.procedure.lifecycle.failed

        finally:
            request_id = time.time()
            summary = ProcedureSummary.from_procedure(self)
            # Queue input arg cannot be pickled, so remove
            pub.sendMessage(
                topic, msg_src=msg_src, request_id=request_id, result=summary
            )

    def start(self):
        """
        Start Procedure execution.

        This calls the run() method in a new child process. Set Procedure state here
        to record state within the parent process. Procedure state is then inherited by
        the child process.
        """
        if self.state is not ProcedureState.CREATED:
            raise Exception(f"Invalid procedure state for run: {self.state}")

        self.change_state(ProcedureState.RUNNING)
        super().start()

    def terminate(self):
        if self.state is not ProcedureState.RUNNING:
            raise Exception(f"Invalid procedure state for terminate: {self.state}")

        self.change_state(ProcedureState.STOPPED)
        super().terminate()

    def change_state(self, new_state: ProcedureState):
        """
        Change procedure state and record change in ProcedureHistory
        """
        self.state = new_state
        self.history.process_states[new_state] = time.time()


@dataclasses.dataclass
class ProcedureSummary:
    """
    ProcedureSummary is a brief representation of a runtime Procedure. It
    captures essential information required to describe a Procedure and to
    distinguish it from other Procedures.
    """

    id: int  # pylint: disable=invalid-name
    script_uri: str
    script_args: typing.Dict[str, ProcedureInput]
    history: ProcedureHistory
    state: ProcedureState

    @staticmethod
    def from_procedure(procedure: Procedure):
        return ProcedureSummary(
            id=procedure.id,
            script_uri=procedure.script_uri,
            script_args=procedure.script_args,
            history=procedure.history,
            state=procedure.state,
        )


class ProcessManager:
    """
    Rules:
     - 0..* prepared processes per manager
     - 0..1 running processes per manager
    """

    def __init__(self):
        self.procedures: typing.OrderedDict[int, Procedure] = OrderedDict()
        self.running: typing.Optional[Procedure] = None
        self.procedure_complete = multiprocessing.Condition()

        self._procedure_factory = ProcedureFactory()
        self._pool = Pool()
        self._scan_id = multiprocessing.Value("i", 1)

    def create(self, script_uri: str, *, init_args: ProcedureInput) -> int:
        """
        Create a new Procedure that will, when executed, run the target Python
        script.

        :param script_uri: script URI, e.g. 'file://myscript.py'
        :param init_args: script initialisation arguments
        :return:
        """
        if not self.procedures:
            pid = 1
        else:
            pid = max(self.procedures.keys()) + 1

        LOGGER.debug(
            "Creating Procedure with pid %d and script_uri %s", pid, script_uri
        )

        procedure = self._procedure_factory.create(
            script_uri, *init_args.args, scan_counter=self._scan_id, **init_args.kwargs
        )
        procedure.id = pid

        # Delete oldest procedure if procedure limit reached
        if len(self.procedures) == PROCEDURE_QUEUE_MAX_LENGTH:
            self.procedures.popitem(last=False)

        self.procedures[pid] = procedure

        return pid

    def run(self, process_id: int, *, run_args: ProcedureInput):
        """
        Run a prepared Procedure.

        This starts execution of the script prepared by a previous create()
        call.

        :param process_id: ID of Procedure to execute
        :param run_args: late-binding arguments to provide to the script
        :return:
        """
        # Use default SIGTEM signal handler which terminates process on first SIGTERM
        # If this is not done we inherit the MainContext signal handler, which requests
        # a co-operative shutdown for the first few attempts before force quitting
        signal.signal(signal.SIGTERM, DEFAULT_SIGTERM_HANDLER)

        if self.running:
            running_pid = self.running.id
            raise ValueError(
                f"Cannot start PID {process_id}: procedure {running_pid} is running"
            )

        try:
            procedure = self.procedures[process_id]
        except KeyError as exc:
            raise ValueError(f"Process {process_id} not found") from exc

        LOGGER.debug("Starting Procedure %d", process_id)

        self.running = procedure
        procedure.script_args["run"] = run_args
        procedure.start()

        def callback(*_):
            # If procedure was stopped, state does not need updated
            if procedure.state is not ProcedureState.STOPPED:
                # Check if an error occurred during process execution
                if not procedure.stacktrace_queue.empty():
                    procedure.history.stacktrace = procedure.stacktrace_queue.get()
                    procedure.change_state(ProcedureState.FAILED)
                else:
                    procedure.change_state(ProcedureState.COMPLETED)
            self.running = None
            with self.procedure_complete:
                self.procedure_complete.notify_all()

        self._pool.apply_async(_wait_for_process, (procedure,), {}, callback, callback)

    def stop(self, process_id):
        """
        stop a running Procedure.

        This stops execution of a currently running script.

        :param process_id: ID of Procedure to stop
        :return:
        """
        if self.running is None:
            raise ValueError(f"Cannot stop PID {process_id}: procedure is not running")

        try:
            procedure = self.procedures[process_id]
        except KeyError as exc:
            raise ValueError(f"Process {process_id} not found") from exc

        LOGGER.debug("Stopping Procedure %d", process_id)

        if procedure.is_alive():
            procedure.terminate()
            # join any potentially zombie process, allowing it to clean up
            multiprocessing.active_children()
            # set running to None here instead of waiting for run() callback
            # so that abort script can be started while callback does clean-up
            self.running = None


def _wait_for_process(process, **_):
    """
    Block until the given process completes.
    :param process: process to wait for
    :param _: unused kwargs
    """
    process.join()


class ProcedureFactory:
    """
    A factory class for creating no-op Procedure objects.
    """

    def create(self, script_uri: str, *args, **kwargs) -> Procedure:
        """
        Create a new Procedure. Right now this just creates the Procedure
        object. In a functional implementation this would create an OS
        (sub)process.

        :param script_uri: URI of Python script to load
        :param args: positional arguments to give to the script process constructor
        :param kwargs: keyword/value arguments to pass to the script process constructor

        :return: Script process object.
        """
        return Procedure(script_uri, *args, **kwargs)


class ModuleFactory:
    """
    Factory class used to return Python Module instances from a variety of
    storage back-ends.
    """

    @staticmethod
    def get_module(script_uri):
        """
        Load Python code from storage, returning an executable Python module.

        :param script_uri: URI of script to load
        :return: Python module
        """
        if script_uri.startswith("test://"):
            loader = ModuleFactory._null_module_loader
        elif script_uri.startswith("file://"):
            loader = ModuleFactory._load_module_from_file
        else:
            raise ValueError("Script URI type not handled: {}".format(script_uri))

        return loader(script_uri)

    @staticmethod
    def _load_module_from_file(script_uri: str) -> types.ModuleType:
        """
        Load Python module from file storage. This module handles file:///
        URIs.

        :param script_uri: URI of script to load.
        :return: Python module
        """
        # remove 'file://' prefix
        path = script_uri[7:]
        loader = importlib.machinery.SourceFileLoader("user_module", path)
        user_module = types.ModuleType(loader.name)
        loader.exec_module(user_module)
        return user_module

    @staticmethod
    def _null_module_loader(_: str) -> types.ModuleType:
        """
        Create and return an empty Python module. Handles test:/// URIs.

        :param _: URI. Will be ignored.
        :return:
        """

        def init(*_, **__):
            pass

        def main(*_, **__):
            pass

        user_module = types.ModuleType("user_module")
        user_module.main = main
        user_module.init = init

        return user_module

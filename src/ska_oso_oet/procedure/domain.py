"""
The ska_oso_oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
import dataclasses
import enum
import importlib.machinery
import logging
import multiprocessing
import os
import signal
import threading
import time
import traceback
import types
import typing
from collections import OrderedDict
from multiprocessing.dummy import Pool

from pubsub import pub

from ska_oso_oet import mptools
from ska_oso_oet.command import SCAN_ID_GENERATOR
from ska_oso_oet.event import topics
from ska_oso_oet.mptools import EventMessage

LOGGER = logging.getLogger(__name__)

PROCEDURE_QUEUE_MAX_LENGTH = 10

DEFAULT_SIGTERM_HANDLER = signal.getsignal(signal.SIGTERM)


class ProcedureState(enum.Enum):
    """
    Represents the script execution state.
    """

    CREATING = enum.auto()
    CREATED = enum.auto()
    RUNNING = enum.auto()
    COMPLETED = enum.auto()
    STOPPED = enum.auto()
    FAILED = enum.auto()
    UNKNOWN = enum.auto()


@dataclasses.dataclass
class GitArgs:
    """
    GitArgs captures information required to identify scripts
    located in git repositories.
    """

    git_repo: typing.Optional[
        str
    ] = "git://gitlab.com/ska-telescope/ska-oso-scripting.git"
    git_branch: typing.Optional[str] = "master"
    git_commit: typing.Optional[str] = None


@dataclasses.dataclass
class FileSystemScript:
    """
    Represents a script in the file system.
    """

    script_uri: str

    def get_type(self):
        return "filesystem"


@dataclasses.dataclass
class GitScript(FileSystemScript):
    """
    Represents a script in a git repository.
    """

    git_args: GitArgs

    def get_type(self):
        return "git"


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
        return "<ProcessHistory(process_states=[{}], stacktrace={})>".format(
            p_history, self.stacktrace
        )


class ScriptWorker(mptools.ProcWorker):
    # Use default SIGTERM signal handler which terminates process on first SIGTERM
    # If this is not done we inherit the MainContext signal handler, which requests
    # a co-operative shutdown for the first few attempts before force quitting
    term_handler = lambda: staticmethod(DEFAULT_SIGTERM_HANDLER)  # noqa: E731

    def __init__(
        self,
        name: str,
        startup_event: multiprocessing.Event,
        shutdown_event: multiprocessing.Event,
        event_q: mptools.MPQueue,
        work_q: mptools.MPQueue,
        script_uri: str,
        *args,
        scan_counter: typing.Optional[multiprocessing.Value] = None,
        **kwargs,
    ):
        self.script_uri = script_uri
        self._scan_counter = scan_counter
        self.work_q = work_q

        self.user_module = ModuleFactory.get_module(script_uri)

        super().__init__(name, startup_event, shutdown_event, event_q, *args, **kwargs)

    def init_args(self, args, kwargs):
        if hasattr(self.user_module, "init"):
            self.user_module.init(*args, **kwargs)

    def startup(self) -> None:
        super().startup()
        msg = EventMessage(
            msg_src=str(os.getpid()), msg_type="LIFECYCLE", msg=ProcedureState.CREATED
        )
        self.event_q.safe_put(msg)

    def shutdown(self):
        super().shutdown()
        msg = EventMessage(
            msg_src=str(os.getpid()), msg_type="LIFECYCLE", msg=ProcedureState.COMPLETED
        )
        self.event_q.safe_put(msg)

    def main_loop(self) -> None:
        """
        main_loop delivers each event received on the work queue to the
        main_func template method, while checking for shutdown notifications.

        Event delivery will cease when the shutdown event is set or a special
        sentinel message is sent.
        """
        self.log(logging.DEBUG, "Entering ScriptWorker.main_loop")

        # stop processing as soon as the shutdown_event is set. Once set, this
        # while loop terminates, thus ending main_loop and starting shutdown
        # of this ProcWorker.
        while not self.shutdown_event.is_set():

            # Get next work item. This call returns after the default safe_get
            # timeout unless an item is in the queue.
            item = self.work_q.safe_get()

            # Go back to the top of the while loop if no message was received,
            # thus checking the shutdown event again.
            if not item:
                continue

            # ok - an item was received from queue
            self.log(logging.DEBUG, f"ScriptWorker.main_loop received '{item}' message")
            # if item is the sentinel message, break to exit out of main_loop
            # and start shutdown
            if item == "END":
                break

            # otherwise call main function with the queue item
            else:
                self.main_func(item)

            # TODO this is a PoC - break after first run
            break

    # Relax pylint as we are deliberately redefining the superclass main_func
    # signature in this specialised subclass. This is intended to be a
    # template, hence the implementation doesn't use item.
    def main_func(
        self, evt: EventMessage
    ):  # pylint: disable=unused-argument,arguments-differ
        if evt.msg_type != "RUN":
            # todo complain about unexpected event type
            return

        run_args: ProcedureInput = evt.msg

        if self._scan_counter:
            SCAN_ID_GENERATOR.backing = self._scan_counter

        msg = EventMessage(
            msg_src=str(os.getpid()), msg_type="LIFECYCLE", msg=ProcedureState.RUNNING
        )
        self.event_q.safe_put(msg)

        # todo publish event messages again
        args = run_args.args
        kwargs = run_args.kwargs
        self.user_module.main(*args, **kwargs)


class Procedure(multiprocessing.Process):
    """
    A Procedure is the OET representation of a Python script, its arguments,
    and its execution state.
    """

    def __init__(
        self,
        script: FileSystemScript,
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
        self.change_state(ProcedureState.CREATING)

        self.user_module = ModuleFactory.get_module(script.script_uri)
        if hasattr(self.user_module, "init"):
            self.user_module.init(*args, **kwargs)

        self.script = script
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
    script: FileSystemScript
    script_args: typing.Dict[str, ProcedureInput]
    history: ProcedureHistory
    state: ProcedureState

    @staticmethod
    def from_procedure(procedure: Procedure):
        return ProcedureSummary(
            id=procedure.id,
            script=procedure.script,
            script_args=procedure.script_args,
            history=procedure.history,
            state=procedure.state,
        )


class ProcessManager:
    def __init__(self):
        self.ctx = mptools.MainContext()

        # mappings of Procs to various identifying metadata
        self.procedures: typing.OrderedDict[int, mptools.Proc] = OrderedDict()
        self.states: typing.Dict[int, ProcedureState] = {}

        # message boxes for manager to each script worker
        self.script_queues: typing.Dict[int, mptools.MPQueue] = {}
        self.history: typing.Dict[int, ProcedureHistory] = {}

        # self.running: typing.Optional[mptools.Proc] = None
        # self.procedure_complete = multiprocessing.Condition()

        # self._pool = Pool()
        self._scan_id = multiprocessing.Value("i", 1)

        status_update_thread = threading.Thread(target=self.status_updater)
        status_update_thread.start()

    @property
    def running(self) -> typing.Optional[mptools.Proc]:
        running_pids = [
            pid for pid, state in self.states.items() if state == ProcedureState.RUNNING
        ]
        if not running_pids:
            return None
        assert len(running_pids) == 1, f"Multiple Procs running: {running_pids}"
        return self.procedures[running_pids[0]]

    def create(self, script_uri: str, *, init_args: ProcedureInput) -> int:
        """
        Create a new Procedure that will, when executed, run the target Python
        script.

        :param script_uri: script URI, e.g. 'file://myscript.py'
        :param init_args: script initialisation arguments
        :return:
        """
        LOGGER.debug("Creating Procedure for script_uri %s", script_uri)

        # msg box for messages from mgr to child, like 'start main()'
        work_q = self.ctx.MPQueue()
        procedure = self.ctx.Proc(
            f"ScriptWorker for {script_uri}",  # name
            ScriptWorker,
            work_q,
            script_uri,
            *init_args.args,
            scan_counter=self._scan_id,
            **init_args.kwargs,
        )
        pid = procedure.proc.pid
        procedure.name = pid
        # todo - rationalise names and PIDs, along with what ID mptools exception handlers should send for failure

        # Delete oldest procedure if procedure limit reached
        if len(self.procedures) == PROCEDURE_QUEUE_MAX_LENGTH:
            deleted_pid, _ = self.procedures.popitem(last=False)
            LOGGER.info("Deleted old PID %d", deleted_pid)
            del self.states[deleted_pid]
            del self.history[deleted_pid]

        self.script_queues[pid] = work_q
        self.procedures[pid] = procedure

        return pid

    def status_updater(self):
        # intended to run in a background thread, updating Proc lifecycle state as events are received
        while not self.ctx.shutdown_event.is_set():
            event: EventMessage = self.ctx.event_queue.safe_get()
            if not event:
                continue

            print(f"Event: {event}")
            if event.msg_type == "LIFECYCLE":
                msg_time: time.time = event.id
                pid = int(event.msg_src)
                new_state: ProcedureState = event.msg
                self.states[pid] = event.msg
                if pid not in self.history:
                    self.history[pid] = ProcedureHistory()
                self.history[pid].process_states[new_state] = msg_time

            elif event.msg_type == "FATAL":
                self.ctx.log(logging.INFO, f"Fatal Event received: {event.msg}")

                msg_time: time.time = event.id
                pid = int(event.msg_src)
                new_state: ProcedureState = ProcedureState.FAILED

                self.states[pid] = new_state
                if pid not in self.history:
                    self.history[pid] = ProcedureHistory()
                self.history[pid].process_states[new_state] = msg_time

            elif event.msg_type == "END":
                self.ctx.log(logging.INFO, f"Shutdown Event received: {event.msg}")
                break

            else:
                self.ctx.log(logging.ERROR, f"Unknown Event: {event}")

    def run(self, process_id: int, *, run_args: ProcedureInput):
        """
        Run a prepared Procedure.

        This starts execution of the script prepared by a previous create()
        call.

        :param process_id: ID of Procedure to execute
        :param run_args: late-binding arguments to provide to the script
        :return:
        """
        running_pid = [
            pid for pid, state in self.states.items() if state == ProcedureState.RUNNING
        ]
        if running_pid:
            raise ValueError(
                f"Cannot start PID {process_id}: procedure {running_pid[0]} is running"
            )

        msg = EventMessage(
            msg_src=self.__class__.__name__, msg_type="RUN", msg=run_args
        )
        LOGGER.debug("Sending start message to PID %d", process_id)
        msg_was_sent = self.script_queues[process_id].safe_put(msg)
        if not msg_was_sent:
            raise ValueError(f"Could not send start message to process {process_id}")

    def stop(self, process_id: int):
        """
        Stop a running Procedure.

        This stops execution of a currently running script.

        :param process_id: ID of Procedure to stop
        :return:
        """
        try:
            procedure = self.procedures[process_id]
            status = self.states[process_id]
        except KeyError as exc:
            raise ValueError(f"Process {process_id} not found") from exc

        if status != ProcedureState.RUNNING:
            raise ValueError(f"Cannot stop PID {process_id}: procedure is not running")

        if procedure.proc.is_alive():
            LOGGER.debug("Stopping Procedure %d", process_id)
            terminated = procedure.terminate(max_retries=3, timeout=0.1)
            final_state = (
                ProcedureState.STOPPED if terminated else ProcedureState.UNKNOWN
            )
            msg = EventMessage(
                msg_src=str(process_id), msg_type="LIFECYCLE", msg=final_state
            )
            self.ctx.event_queue.safe_put(msg)

            # join any potentially zombie process, allowing it to clean up
            multiprocessing.active_children()


class OldProcessManager:
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

    def create(
        self,
        script: FileSystemScript,
        *,
        init_args: ProcedureInput,
    ) -> int:
        """
        Create a new Procedure that will, when executed, run the target Python
        script.

        :param script: FileSystemScript object containing script_uri (e.g. 'file://myscript.py')
        and information on script execution environment (e.g. git_args in GitScript)
        :param init_args: script initialisation arguments
        :return:
        """
        if not self.procedures:
            pid = 1
        else:
            pid = max(self.procedures.keys()) + 1

        LOGGER.debug(
            "Creating Procedure with pid %d and script_uri %s", pid, script.script_uri
        )

        procedure = self._procedure_factory.create(
            script,
            *init_args.args,
            scan_counter=self._scan_id,
            **init_args.kwargs,
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

    def create(self, script: FileSystemScript, *args, **kwargs) -> Procedure:
        """
        Create a new Procedure. Right now this just creates the Procedure
        object. In a functional implementation this would create an OS
        (sub)process.

        :param script: FileSystemScript object of Python script to load
        :param args: positional arguments to give to the script process constructor
        :param kwargs: keyword/value arguments to pass to the script process constructor

        :return: Script process object.
        """
        return Procedure(script, *args, **kwargs)


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
        elif script_uri.startswith("git://"):
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
        if "git" in script_uri:
            path = script_uri[6:]
        else:
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

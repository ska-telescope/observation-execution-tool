"""
The ska_oso_oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
import copy
import dataclasses
import enum
import errno
import importlib.machinery
import itertools
import logging
import multiprocessing
import os
import signal
import subprocess
import sys
import threading
import time
import types
from typing import Dict, List, Optional, Tuple

from ska_oso_oet import mptools
from ska_oso_oet.command import SCAN_ID_GENERATOR
from ska_oso_oet.mptools import EventMessage
from ska_oso_oet.procedure.environment import Environment, EnvironmentManager
from ska_oso_oet.procedure.gitmanager import GitArgs, GitManager

LOGGER = logging.getLogger(__name__)

HISTORY_MAX_LENGTH = 10

DEFAULT_SIGTERM_HANDLER = signal.getsignal(signal.SIGTERM)


def script_signal_handler(
    signal_object,
    exception_class,
    signal_num: int,  # pylint: disable=unused-argument
    current_stack_frame,
) -> None:
    """
    Custom signal handling function that simply raises an exception.
    Assuming the running Python script does not catch this exception, it
    will interrupt script execution and result in termination of that script.

    We don't want all sibling script processes to terminate, hence no setting
    of shutdown_event is done in this handler.

    :param signal_object: SignalObject to modify to reflect signal-handling
        state
    :param exception_class: Exception type to raise when call limit is
        exceeded
    :param signal_num: POSIX signal ID
    :param current_stack_frame: current stack frame
    """
    raise exception_class()


class ProcedureState(enum.Enum):
    """
    Represents the script execution state.
    """

    UNKNOWN = enum.auto()
    IDLE = enum.auto()
    CREATING = enum.auto()
    PREP_ENV = enum.auto()
    LOADING = enum.auto()
    READY = enum.auto()
    RUNNING = enum.auto()
    COMPLETED = enum.auto()
    STOPPED = enum.auto()
    FAILED = enum.auto()


class LifecycleMessage(EventMessage):
    """
    LifecycleMessage is a message type for script lifecycle events.
    """

    def __init__(self, msg_src: str, new_state: ProcedureState):
        super().__init__(msg_src, "LIFECYCLE", new_state)


@dataclasses.dataclass
class ExecutableScript:
    """
    Base class for all executable scripts.

    Expected specialisations:

    - scripts on filesystem
    - scripts in git repository
    - scripts given as a string
    - scripts stored in the ODA
    - etc.
    """


@dataclasses.dataclass
class FileSystemScript(ExecutableScript):
    """
    Represents a script stored on the file system.
    """

    script_uri: str

    def __post_init__(self):
        if not self.script_uri.startswith(self.get_prefix()):
            raise ValueError(
                f"Incorrect prefix for {self.__class__.__name__}: {self.script_uri}"
            )

    def get_type(self):
        return "filesystem"

    def get_prefix(self):
        return "file://"


@dataclasses.dataclass
class GitScript(FileSystemScript):
    """
    Represents a script in a git repository.
    """

    git_args: GitArgs
    default_git_env: Optional[bool] = True

    def get_type(self):
        return "git"

    def get_prefix(self):
        return "git://"


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

    def __init__(
        self,
        process_states: Optional[List[Tuple[ProcedureState, float]]] = None,
        stacktrace=None,
    ):
        if process_states is None:
            process_states = []
        self.process_states = process_states
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
            ["({!s}, {!r})".format(s, t) for (s, t) in self.process_states]
        )
        return "<ProcessHistory(process_states=[{}], stacktrace={})>".format(
            p_history, self.stacktrace
        )


class ScriptWorker(mptools.ProcWorker):
    # install our custom signal handler that raises an exception on SIGTERM
    term_handler = staticmethod(script_signal_handler)  # noqa: E731

    def __init__(
        self,
        name: str,
        startup_event: multiprocessing.Event,
        shutdown_event: multiprocessing.Event,
        event_q: mptools.MPQueue,
        work_q: mptools.MPQueue,
        *args,
        scan_counter: Optional[multiprocessing.Value] = None,
        environment: Optional[Environment] = None,
        **kwargs,
    ):
        self.name = name
        self._scan_counter = scan_counter
        self._environment = environment
        self.work_q = work_q

        # user_module will be set on LOAD message
        self.user_module = None

        super().__init__(name, startup_event, shutdown_event, event_q, *args, **kwargs)

    def publish_lifecycle(self, new_state: ProcedureState):
        msg = LifecycleMessage(self.name, new_state)
        self.event_q.safe_put(msg)

    def init_args(self, args, kwargs):
        self.init_input = ProcedureInput(*args, **kwargs)

    def startup(self) -> None:
        super().startup()
        self.publish_lifecycle(ProcedureState.IDLE)

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

        try:
            while not self.shutdown_event.is_set():

                # Get next work item. This call returns after the default safe_get
                # timeout unless an item is in the queue.
                item = self.work_q.safe_get()

                # Go back to the top of the while loop if no message was received,
                # thus checking the shutdown event again.
                if not item:
                    continue

                # ok - an item was received from queue
                self.log(
                    logging.DEBUG, f"ScriptWorker.main_loop received '{item}' message"
                )
                # if item is the sentinel message, break to exit out of main_loop
                # and start shutdown
                if item == "END":
                    break

                # otherwise call main function with the queue item
                else:
                    ret = self.main_func(item)
                    if ret == StopIteration:
                        self.publish_lifecycle(ProcedureState.COMPLETED)
                        break

        except mptools.TerminateInterrupt:
            # raised by the signal handler on Proc.terminate()
            pass

    # Relax pylint as we are deliberately redefining the superclass main_func
    # signature in this specialised subclass. This is intended to be a
    # template, hence the implementation doesn't use item.
    def main_func(
        self, evt: EventMessage
    ):  # pylint: disable=unused-argument,arguments-differ

        if evt.msg_type not in ("ENV", "LOAD", "RUN"):
            self.log(logging.WARN, "Unexpected message: %s", evt)
            return

        if self._scan_counter:
            SCAN_ID_GENERATOR.backing = self._scan_counter

        if evt.msg_type == "ENV":
            self.publish_lifecycle(ProcedureState.PREP_ENV)
            if self._environment is None:
                raise RuntimeError("Install failed, environment has not been defined")
            if not self._environment.created.is_set():
                if not self._environment.creating.is_set():
                    self._environment.creating.set()
                    script = evt.msg

                    if not isinstance(script, GitScript):
                        raise RuntimeError(
                            "Cannot create virtual environment for script type"
                            f" {script.__class__.__name__}"
                        )

                    clone_dir = GitManager.clone_repo(script.git_args)
                    sys.path.insert(0, self._environment.site_packages)

                    try:
                        # Upgrade pip version, venv uses a pre-packaged pip which is outdated
                        subprocess.check_output(
                            [
                                f"{self._environment.location}/bin/pip",
                                "install",
                                "--index-url=https://pypi.org/simple",
                                "--upgrade",
                                "pip",
                            ]
                        )
                        if os.path.exists(clone_dir + "/pyproject.toml"):
                            # Convert poetry requirements into a requirements.txt file
                            subprocess.check_output(
                                [
                                    "poetry",
                                    "export",
                                    "--output",
                                    "requirements.txt",
                                    "--without-hashes",
                                ],
                                cwd=clone_dir,
                            )
                        subprocess.check_output(
                            [f"{self._environment.location}/bin/pip", "install", "."],
                            cwd=clone_dir,
                        )
                    except subprocess.CalledProcessError as e:
                        raise RuntimeError(
                            "Something went wrong during script environment"
                            f" installation: {e.output}"
                        ) from None
                        # TODO: How to handle if another process is waiting on created_condition but install fails?
                    self._environment.created.set()
                else:
                    self._environment.created.wait()
            self.publish_lifecycle(ProcedureState.IDLE)

        if evt.msg_type == "LOAD":
            self.publish_lifecycle(ProcedureState.LOADING)
            script: ExecutableScript = evt.msg
            self.log(logging.DEBUG, "Loading user script %s", script)
            try:
                self.user_module = ModuleFactory.get_module(script)
            except FileNotFoundError:
                raise FileNotFoundError(
                    errno.ENOENT, os.strerror(errno.ENOENT), script.script_uri
                ) from None
            self.publish_lifecycle(ProcedureState.IDLE)

        if evt.msg_type == "RUN":
            fn_name, fn_args = evt.msg

            # special case: get init args from instance, check for method.
            # we may want to revisit whether init remains a special case
            if fn_name == "init":
                if not hasattr(self.user_module, "init"):
                    self.publish_lifecycle(ProcedureState.READY)
                    return
                fn_args = self.init_input

            self.log(
                logging.DEBUG,
                "Calling user function %s",
                repr(fn_args).replace("<ProcedureInput", fn_name)[:-1],
            )
            self.publish_lifecycle(ProcedureState.RUNNING)
            fn = getattr(self.user_module, fn_name)
            fn(*fn_args.args, **fn_args.kwargs)
            self.publish_lifecycle(ProcedureState.READY)

            # to be refined. indicates that script can not be rerun, thus allowing
            # the ScriptWorker to complete. other script might be rerun and go back
            # to idle
            if fn_name == "main":
                return StopIteration


@dataclasses.dataclass
class ArgCapture:
    fn: str
    fn_args: ProcedureInput
    time: float


@dataclasses.dataclass
class ProcedureSummary:
    """
    ProcedureSummary is a brief representation of a runtime Procedure. It
    captures essential information required to describe a Procedure and to
    distinguish it from other Procedures.
    """

    id: int  # pylint: disable=invalid-name
    script: ExecutableScript
    script_args: List[ArgCapture]
    history: ProcedureHistory
    state: ProcedureState


class ProcessManager:
    """"""

    def __init__(self):
        self.ctx = mptools.MainContext()

        self._pid_counter = itertools.count(1)
        self.em = EnvironmentManager()

        # mappings of Procs to various identifying metadata
        self.procedures: Dict[int, mptools.Proc] = {}
        self.states: Dict[int, ProcedureState] = {}
        self.script_args: Dict[int, List[ArgCapture]] = {}
        self.scripts: Dict[int, ExecutableScript] = {}
        self.environments: Dict[int, Environment] = {}

        # message boxes for manager to each script worker
        self.script_queues: Dict[int, mptools.MPQueue] = {}
        self.history: Dict[int, ProcedureHistory] = {}

        self._scan_id = multiprocessing.Value("i", 1)

        self._state_updating = threading.Lock()
        status_update_thread = threading.Thread(
            target=self.status_updater, name="StatusUpdate"
        )
        status_update_thread.start()

    def _summarise(self, pid: int) -> ProcedureSummary:
        state = self.states[pid]
        script = self.scripts[pid]
        # deepcopy to prevent returned copies being modified
        script_args = copy.deepcopy(self.script_args[pid])
        history = copy.deepcopy(self.history[pid])
        return ProcedureSummary(
            id=pid, script=script, script_args=script_args, history=history, state=state
        )

    def summarise(self, pids: Optional[List[int]] = None) -> List[ProcedureSummary]:
        """
        Return ProcedureSummary objects for Procedures with the requested IDs.

        This method accepts an optional list of integers, representing the
        Procedure IDs to summarise. If the pids is left undefined,
        ProcedureSummary objects for all current Procedures will be returned.

        :param pids: optional list of Procedure IDs to summarise.
        :return: list of ProcedureSummary objects
        """
        # freeze state to prevent mutation from events
        with self._state_updating:
            all_pids = self.states.keys()
            if pids is None:
                pids = all_pids

            missing_pids = {p for p in pids if p not in all_pids}
            if missing_pids:
                raise ValueError(f"Process IDs not found: {missing_pids}")

            return [self._summarise(pid) for pid in pids]

    @property
    def running(self) -> Optional[mptools.Proc]:
        running_pids = [
            pid for pid, state in self.states.items() if state == ProcedureState.RUNNING
        ]
        if not running_pids:
            return None
        assert len(running_pids) == 1, f"Multiple Procs running: {running_pids}"
        return self.procedures[running_pids[0]]

    def create(self, script: ExecutableScript, *, init_args: ProcedureInput) -> int:
        """
        Create a new Procedure that will, when executed, run the target Python
        script.

        Objects that can only be shared through inheritance, such as multiprocessing
        object, can be shared by providing them as init_args here. These arguments will
        be provided to the init function in the user script, where present.

        :param script: script URI, e.g. 'file://myscript.py'
        :param init_args: script initialisation arguments
        :return:
        """
        pid = next(self._pid_counter)
        LOGGER.debug("Creating ScriptWorker #%s for %s", pid, script)

        now = time.time()
        self.scripts[pid] = script
        self.states[pid] = ProcedureState.CREATING
        self.history[pid] = ProcedureHistory([(ProcedureState.CREATING, now)])
        self.script_args[pid] = [ArgCapture(fn="init", fn_args=init_args, time=now)]

        # msg box for messages from manager to child, like 'run main function'
        work_q = self.ctx.MPQueue()
        self.script_queues[pid] = work_q

        # prime the work queue with an initial message instructing it to set up environment,
        # load the child script and run init function of the script
        msg_src = self.__class__.__name__

        env = None
        if isinstance(script, GitScript) and not script.default_git_env:
            env = self.em.create_env(script.git_args)
            env_msg = EventMessage(msg_src=msg_src, msg_type="ENV", msg=script)
            work_q.safe_put(env_msg)

            self.environments[pid] = env

        load_msg = EventMessage(msg_src=msg_src, msg_type="LOAD", msg=script)
        work_q.safe_put(load_msg)
        # ... and also to execute init
        init_msg = EventMessage(msg_src=msg_src, msg_type="RUN", msg=("init", None))
        work_q.safe_put(init_msg)

        # Runtime error will be raised if Proc creation fails
        # TODO close and delete work_q, etc. on failure?
        procedure = self.ctx.Proc(
            str(pid),
            ScriptWorker,
            work_q,
            *init_args.args,
            scan_counter=self._scan_id,
            environment=env,
            **init_args.kwargs,
        )

        # Proc creation was successful. Continue.
        self.procedures[pid] = procedure

        self._prune_old_state()

        return pid

    def _prune_old_state(self):
        """
        Remove the state associated with the oldest deletable Procedures so
        that the state history remains below the history limit
        HISTORY_MAX_LENGTH.

        Note that we inspect the states dict. The entries for individual
        processes are created and updated in a separate thread.

        TODO: maintenance could also be done in the status update thread?
        """
        # Delete oldest deletable procedure if procedure limit reached
        deletable_states = [
            ProcedureState.COMPLETED,
            ProcedureState.FAILED,
            ProcedureState.STOPPED,
            ProcedureState.UNKNOWN,
        ]

        with self._state_updating:
            if len(self.states) > HISTORY_MAX_LENGTH:
                lower_bound = len(self.states) - HISTORY_MAX_LENGTH
                pids_to_consider = list(self.states.keys())[:lower_bound]
                to_delete = {
                    old_pid
                    for old_pid in pids_to_consider
                    if self.states.get(old_pid, None) in deletable_states
                }

                for old_pid in to_delete:
                    self.ctx.log(
                        logging.DEBUG,
                        "Deleting state for %s PID #%s",
                        self.states[old_pid].name,
                        old_pid,
                    )
                    del self.states[old_pid]
                    del self.history[old_pid]
                    del self.script_args[old_pid]
                    del self.scripts[old_pid]

    # TODO make this function an instance of threading.Thread so that update_history
    # and cleanup can be methods on that class?
    def status_updater(self):
        deletable_states = [
            ProcedureState.COMPLETED,
            ProcedureState.FAILED,
            ProcedureState.STOPPED,
            ProcedureState.UNKNOWN,
        ]

        def update_history(event: EventMessage, new_state: ProcedureState):
            msg_time: time.time = event.id
            pid = int(event.msg_src)
            self.states[pid] = new_state
            self.history[pid].process_states.append((new_state, msg_time))

        def cleanup(event: EventMessage, new_state: ProcedureState):
            # clean up mptools resources
            if new_state in deletable_states:
                pid = int(event.msg_src)
                q = self.script_queues[pid]
                del self.script_queues[pid]
                self.ctx.queues.remove(q)
                q.safe_close()
                del self.procedures[pid]

        # intended to run in a background thread, updating Proc lifecycle state as events are received
        while not self.ctx.shutdown_event.is_set():
            event: EventMessage = self.ctx.event_queue.safe_get()
            if not event:
                continue

            self.ctx.log(
                logging.DEBUG,
                "Handling %s %s event: %s",
                event.msg_src,
                event.msg_type,
                event.msg,
            )

            if event.msg_type == "LIFECYCLE":
                new_state = event.msg
                with self._state_updating:
                    update_history(event, new_state)
                    cleanup(event, new_state)

            elif event.msg_type == "FATAL":
                self.ctx.log(logging.INFO, f"Fatal Event received: {event.msg}")
                pid = int(event.msg_src)
                with self._state_updating:
                    update_history(event, ProcedureState.FAILED)
                    self.history[pid].stacktrace = event.msg
                    cleanup(event, ProcedureState.FAILED)

            elif event.msg_type == "END":
                self.ctx.log(logging.INFO, f"Shutdown Event received: {event.msg}")
                break

            else:
                self.ctx.log(logging.ERROR, f"Unhandled event: {event}")

    def run(self, process_id: int, *, call: str, run_args: ProcedureInput) -> None:
        """
        Run a prepared Procedure.

        This starts execution of the script prepared by a previous create()
        call.

        :param process_id: ID of Procedure to execute
        :param call: name of function to call
        :param run_args: late-binding arguments to provide to the script
        :return:
        """
        if process_id not in self.states:
            raise ValueError(f"PID #{process_id} not found")

        if self.states[process_id] != ProcedureState.READY:
            raise ValueError(
                f"PID #{process_id} unrunnable in state {self.states[process_id]}"
            )

        running_pid = [
            (pid, state)
            for pid, state in self.states.items()
            if state == ProcedureState.RUNNING
        ]
        if running_pid:
            pid, state = running_pid[0]
            raise ValueError(f"Cannot start PID {process_id}: PID #{pid} is {state}")

        msg = EventMessage(
            msg_src=self.__class__.__name__, msg_type="RUN", msg=(call, run_args)
        )
        LOGGER.debug("Sending 'run %s' message to PID %d", call, process_id)
        msg_was_sent = self.script_queues[process_id].safe_put(msg)
        if not msg_was_sent:
            raise ValueError(f"Could not send start message to process {process_id}")

        self.script_args[process_id].append(
            ArgCapture(fn=call, fn_args=run_args, time=time.time())
        )

    def stop(self, process_id: int) -> None:
        """
        Stop a running Procedure.

        This stops execution of a currently running script.

        :param process_id: ID of Procedure to stop
        :return:
        """
        try:
            procedure = self.procedures[process_id]
            state = self.states[process_id]
        except KeyError as exc:
            raise ValueError(f"Process {process_id} not found") from exc

        stoppable_states = [
            ProcedureState.IDLE,
            ProcedureState.READY,
            ProcedureState.RUNNING,
            ProcedureState.LOADING,
        ]
        if state not in stoppable_states:
            raise ValueError(f"Cannot stop PID {process_id} with state {state.name}")

        if procedure.proc.is_alive():
            LOGGER.debug("Stopping Procedure %d", process_id)
            terminated = procedure.terminate(max_retries=3, timeout=0.1)
            final_state = (
                ProcedureState.STOPPED if terminated else ProcedureState.UNKNOWN
            )
            msg = EventMessage(
                msg_src=procedure.proc.name, msg_type="LIFECYCLE", msg=final_state
            )
            self.ctx.event_queue.safe_put(msg)

            # join any potentially zombie process, allowing it to clean up
            multiprocessing.active_children()

    def shutdown(self):
        # TODO: Find a better way to exit the PM MainContext
        self.ctx.__exit__(None, None, None)


class ModuleFactory:
    """
    Factory class used to return Python Module instances from a variety of
    storage back-ends.
    """

    @staticmethod
    def get_module(script: ExecutableScript):
        """
        Load Python code from storage, returning an executable Python module.

        :param script: Script object describing the script to load
        :return: Python module
        """
        if isinstance(script, GitScript):
            loader = ModuleFactory._load_module_from_git
            return loader(script)
        if isinstance(script, FileSystemScript):
            loader = ModuleFactory._load_module_from_file
            return loader(script.script_uri)

        raise ValueError(f"Script type not handled: {script.__class__.__name__}")

    @staticmethod
    def _load_module_from_file(script_uri: str) -> types.ModuleType:
        """
        Load Python module from file storage. This module handles file://
        and git:// URIs.

        :param script_uri: URI of script to load.
        :return: Python module
        """
        # remove prefix
        path = script_uri[7:]
        loader = importlib.machinery.SourceFileLoader("user_module", path)
        user_module = types.ModuleType(loader.name)
        loader.exec_module(user_module)
        return user_module

    @staticmethod
    def _load_module_from_git(script: GitScript) -> types.ModuleType:
        """
        Load Python module from a git repository. Clones the repository if repo has not yet
        been cloned. The repository will not have been cloned if default environment is being
        used. This module handles git:// URIs.

        :param script: GitScript object with information on script location
        :return: Python module
        """
        clone_path = GitManager.clone_repo(script.git_args)

        # remove prefix and any leading slashes
        relative_script_path = script.script_uri[len(script.get_prefix()) :].lstrip("/")
        script_path = clone_path + "/" + relative_script_path

        loader = importlib.machinery.SourceFileLoader("user_module", script_path)
        user_module = types.ModuleType(loader.name)
        loader.exec_module(user_module)
        return user_module

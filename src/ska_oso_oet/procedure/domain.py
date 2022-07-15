# BTN-1394
"""
The ska_oso_oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
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
import types
from typing import Callable, Dict, List, Optional, Type

from pubsub import pub

from ska_oso_oet import mptools
from ska_oso_oet.command import SCAN_ID_GENERATOR
from ska_oso_oet.mptools import EventMessage
from ska_oso_oet.procedure.environment import Environment, EnvironmentManager
from ska_oso_oet.procedure.gitmanager import GitArgs, GitManager

LOGGER = logging.getLogger(__name__)

# Maximum time allowed for environment creation. Note that environment
# creation must succeed within this period or creation will be considered as
# failed, regardless of the current status of that installation process.
# Experience shows that the default timeout of 600 secs (10 minutes) is more
# than sufficient for any standard Python project. Installing a project that
# required compilation, such as a project that depends on a new version of
# Tango, could in principle exceed this timeout. However, as the Docker image
# does not include compiler tools, compilation is not possible anyway.
ENV_CREATION_TIMEOUT_SECS = 600.0

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
    COMPLETE = enum.auto()
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
    create_env: Optional[bool] = False

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


class ScriptWorker(mptools.ProcWorker):
    """
    ScriptWorker loads user code in a child process, running functions of that
    user code on request.

    ScriptWorker acts when a message is received on its work queue. It responds to four
    types of messages:

    1. LOAD - to load the specified code in this process
    2. ENV - to install the dependencies for the specified script in this process
    3. RUN - to run the named function in this process
    4. PUBSUB - external pubsub messages that should be published locally

    ScriptWorker converts external inter-process mptool pub/sub messages to
    intra-process pypubsub pub/sub messages. That is, EventMessages received on the
    local work queue are rebroadcast locally as pypubsub messages. Likewise, the
    ScriptWorker listens to all pypubsub messages broadcast locally,
    converts them to pub/sub EventQueue messages, and puts them on the 'main'
    queue for transmission to other interested ScriptWorkers.
    """

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
        # Message is rolled by hand and sent via a direct message to the
        # ProcessManager as we want to announce CREATING at the earliest
        # possible moment; we can't announce via pypubsub just yet as the
        # intraprocess<->interprocess republish function is not registered
        # till later in the construction process
        msg = EventMessage(
            msg_src=name,
            msg_type="PUBSUB",
            msg=dict(
                topic="procedure.lifecycle.statechange",
                kwargs=dict(new_state=ProcedureState.CREATING),
            ),
        )
        event_q.put(msg)

        self.name = name

        self._scan_counter = scan_counter
        self._environment = environment
        self.work_q = work_q

        # user_module will be set on LOAD message
        self.user_module = None

        super().__init__(name, startup_event, shutdown_event, event_q, *args, **kwargs)

        # AT2-591. The forked process inherits all subscriptions of the
        # parent, which we do not want to maintain in this child process. This
        # could be done before super().__init__() at the expense of losing the
        # log message, as logging is set up in the super constructor
        unsubscribed = pub.unsubAll()
        self.log(
            logging.DEBUG,
            "Unsubscribed %s pypubsub subscriptions in Procedure #%s (PID=%s)",
            len(unsubscribed),
            self.name,
            os.getpid(),
        )

        # Register a callback function so that all pypubsub messages broadcast
        # in this process are also queued for distribution to remote processes
        pub.subscribe(self.republish, pub.ALL_TOPICS)

    def init_args(self, args, kwargs):
        self.init_input = ProcedureInput(*args, **kwargs)

    def startup(self) -> None:
        super().startup()

        # mark state as IDLE to signify that this child process started up
        # successfully
        self.publish_lifecycle(ProcedureState.IDLE)

    def shutdown(self) -> None:
        super().shutdown()

        # Technically, unsubscribing is unnecessary as pypubsub holds weak
        # references to listeners and automatically unsubscribes listeners
        # that have been deleted
        pub.unsubscribe(self.republish, pub.ALL_TOPICS)

    def publish_lifecycle(self, new_state: ProcedureState):
        """
        Broadcast a lifecycle status change event.

        :param new_state: new lifecycle state
        """
        # This message could be broadcast on pypubsub, letting the republish
        # callback rebroadcast it on the mptools bus. But, we know there are no
        # local subscribers so bypass the pypubsub step and broadcast directly to
        # the inter-process event bus.
        # pub.sendMessage(
        #     topics.procedure.lifecycle.statechange,
        #     msg_src=self.name,
        #     new_state=new_state,
        # )
        msg = EventMessage(
            msg_src=self.name,
            msg_type="PUBSUB",
            msg=dict(
                topic="procedure.lifecycle.statechange",
                kwargs=dict(new_state=new_state),
            ),
        )
        self.event_q.put(msg)

    def republish(self, topic: pub.Topic = pub.AUTO_TOPIC, **kwargs) -> None:
        """
        Republish a local pypubsub event over the inter-process mptools event
        bus.

        :param topic: message topic, set automatically by pypubsub
        :param kwargs: any metadata associated with pypubsub message
        :return:
        """
        # avoid infinite loop - do not republish external events
        try:
            msg_src = kwargs.pop("msg_src")
        except KeyError:
            # No message source = virgin event published on pypubsub
            msg_src = self.name

        # ... but if this is a local message (message source = us), send it
        # out to the main queue and hence on to other EventBusWorkers
        if msg_src == self.name:
            # Convert pypubsub event to the equivalent mptools EventMessage
            msg = EventMessage(
                self.name, "PUBSUB", dict(topic=topic.name, kwargs=kwargs)
            )

            # not that this is a blocking put. If the queue is full, this call
            # will block until the queue has room to accept the message
            self.log(logging.DEBUG, "Republishing local pypubsub event: %s", msg)
            self.event_q.put(msg)

    def _on_pubsub(self, evt: EventMessage) -> None:
        # take the work item - the external pub/sub EventMessage - and
        # rebroadcast it locally as a pypubsub message, avoiding an infinite
        # loop by ignoring events that originated from us.
        if evt.msg_src != self.name:
            self.log(logging.DEBUG, "Republishing external event: %s", evt)
            payload = evt.msg
            topic = payload["topic"]
            pub.sendMessage(topic, msg_src=evt.msg_src, **payload["kwargs"])
        else:
            self.log(logging.DEBUG, "Discarding internal event: %s", evt)

    def _on_env(self, evt: EventMessage) -> None:
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
                    if os.path.exists(os.path.join(clone_dir, "pyproject.toml")):
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
                # Environment is being created by another script. Wait for the
                # other process to finish environment installation before proceeding.
                # Throw a timeout error if env creation takes too long, likely means that
                # the environment installation has failed
                self._environment.created.wait(timeout=ENV_CREATION_TIMEOUT_SECS)

        sys.path.insert(0, self._environment.site_packages)
        self.publish_lifecycle(ProcedureState.IDLE)

    def _on_load(self, evt: EventMessage) -> None:
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

    def _on_run(self, evt: EventMessage) -> Optional[Type[StopIteration]]:
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
        # the ScriptWorker to complete. other scripts might be rerun and go back
        # to idle
        if fn_name == "main":
            return StopIteration

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

                # otherwise handle the event based on type
                else:
                    if item.msg_type not in ("LOAD", "RUN", "PUBSUB", "ENV"):
                        self.log(logging.WARN, "Unexpected message: %s", item)
                        return

                    if self._scan_counter:
                        SCAN_ID_GENERATOR.backing = self._scan_counter

                    if item.msg_type == "PUBSUB":
                        self._on_pubsub(item)

                    if item.msg_type == "ENV":
                        self._on_env(item)

                    if item.msg_type == "LOAD":
                        self._on_load(item)

                    if item.msg_type == "RUN":
                        ret = self._on_run(item)
                        if ret == StopIteration:
                            break

        except mptools.TerminateInterrupt:
            # raised by the signal handler on Proc.terminate()
            pass

        else:
            self.publish_lifecycle(ProcedureState.COMPLETE)


class ProcessManager:
    """
    ProcessManager is the parent for all ScriptWorker processes.

    ProcessManager is responsible for launching ScriptWorker processes and
    communicating API requests such as 'run main() function' or 'stop
    execution' to the running scripts. If a script execution process does
    not respond to the request, the process will be forcibly terminated.
    ProcessManager delegates to the mptools framework for process
    management functionality. Familiarity with mptools is useful in
    understanding ProcessManager functionality.

    ProcessManager is also responsible for communicating script events to
    the rest of the system, such as events issued by the script or related
    to the script execution lifecycle.

    It is recommended that ProcessManager.shutdown() be called before the
    ProcessManager is garbage collected. Failure to call shutdown could break
    the any multiprocessing state held in the scope of the manager or its
    child processes. This may or may not be a problem, depending on what is
    held and whether that state is used elsewhere. In short, be safe and call
    shutdown().

    Note: ProcessManager does not maintain a history of script execution.
    History is recorded and managed by the ScriptExecutionService.
    """

    def __init__(
        self,
        mp_context: Optional[multiprocessing.context.BaseContext] = None,
        on_pubsub: Optional[List[Callable[[EventMessage], None]]] = None,
    ):
        """
        Create a new ProcessManager.

        Functions passed in the on_pubsub argument will be called by the
        ProcessManager every time the ProcessManager's message loop receives
        a PUBSUB EventMessage. Callbacks should not perform significant
        processing on the same thread, as this would block the ProcessManager
        event loop.

        :param mp_context: multiprocessing context use to create
            multiprocessing primitives
        :param on_pubsub: functions to call when a PUBSUB message is received
        """
        self.ctx = mptools.MainContext(mp_context)

        # counter used to generate process ID for new processes
        self._pid_counter = itertools.count(1)

        # mapping of Proc ID to Proc
        self.procedures: Dict[int, mptools.Proc] = {}

        # message boxes for manager to each script worker
        self.script_queues: Dict[int, mptools.MPQueue] = {}

        # maps Proc ID to current state
        self.states: Dict[int, ProcedureState] = {}

        # maps Proc IDs to venv environment
        self.em = EnvironmentManager(mp_context)
        self.environments: Dict[int, Environment] = {}

        self._scan_id = multiprocessing.Value("i", 1)

        self._state_updating = threading.RLock()

        # allow clients to add listeners to pubsub messages. This is necessary
        # to inject a callback that can bridge MainContext message queues
        # We do not register _update_state as a pypubsub subscription as
        # it may then be invoked by other publications of that same event, for
        # instance when the SESWorker's EventBusWorker queue publishes it
        self._on_pubsub = [self._publish_as_pypubsub, self._update_state]
        if on_pubsub is not None:
            self._on_pubsub.extend(on_pubsub)

        message_loop = threading.Thread(target=self.message_loop, name="Message Loop")
        message_loop.start()

    def _publish_as_pypubsub(self, event: EventMessage) -> None:
        """
        Publish an mptools EventMessage locally as a pypubsub message.

        :param event: EventMessage to republish
        """
        payload = event.msg
        topic = payload["topic"]
        pub.sendMessage(topic, msg_src=event.msg_src, **payload["kwargs"])

    def _on_fatal(self, event: EventMessage) -> None:
        # event needs to be added to the queue so that other listeners
        # can process it, otherwise we'd call update_state_do
        # self._update_state_and_cleanup(int(event.msg_src), ProcedureState.FAILED)
        self.ctx.event_queue.put(
            EventMessage(
                msg_src=event.msg_src,
                msg_type="PUBSUB",
                msg=dict(
                    topic="procedure.lifecycle.statechange",
                    kwargs=dict(new_state=ProcedureState.FAILED),
                ),
            )
        )

        # announce stacktrace for any interested parties
        self.ctx.event_queue.put(
            EventMessage(
                msg_src=event.msg_src,
                msg_type="PUBSUB",
                msg=dict(
                    topic="procedure.lifecycle.stacktrace",
                    kwargs=dict(stacktrace=event.msg),
                ),
            )
        )

        # pub.sendMessage(
        #     topics.procedure.lifecycle.stacktrace,
        #     msg_src=event.msg_src,
        #     stacktrace=event.msg,
        # )

    def _update_state_and_cleanup(self, pid: int, new_state: ProcedureState):
        deletable_states = [
            ProcedureState.COMPLETE,
            ProcedureState.FAILED,
            ProcedureState.STOPPED,
            ProcedureState.UNKNOWN,
        ]

        with self._state_updating:
            self.states[pid] = new_state

            # clean up mptools resources
            if new_state in deletable_states:
                q = self.script_queues[pid]
                del self.script_queues[pid]
                self.ctx.queues.remove(q)
                q.safe_close()
                del self.procedures[pid]
                del self.states[pid]

    def _update_state(self, event: EventMessage):
        """
        Update Procedure state in response to a procedure.lifecycle.statechange
        event.

        :param event: EventMessage to process
        """
        payload = event.msg
        if payload.get("topic", None) != "procedure.lifecycle.statechange":
            return

        pid = int(event.msg_src)
        new_state = payload["kwargs"]["new_state"]
        self._update_state_and_cleanup(pid, new_state)

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

        # msg box for messages from manager to child, like 'run main function'
        work_q = self.ctx.MPQueue()

        # prime the work queue with an initial message instructing it to set up environment,
        # load the child script and run init function of the script
        msg_src = self.__class__.__name__

        env = None
        if isinstance(script, GitScript) and script.create_env:
            env = self.em.create_env(script.git_args)
            env_msg = EventMessage(msg_src=msg_src, msg_type="ENV", msg=script)
            work_q.safe_put(env_msg)

            self.environments[pid] = env

        load_msg = EventMessage(msg_src=msg_src, msg_type="LOAD", msg=script)
        work_q.safe_put(load_msg)
        # ... and also to execute init
        init_msg = EventMessage(msg_src=msg_src, msg_type="RUN", msg=("init", None))
        work_q.safe_put(init_msg)

        self.script_queues[pid] = work_q
        self.states[pid] = ProcedureState.CREATING

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

        # Proc creation was successful. Can store procedure and continue.
        self.procedures[pid] = procedure

        return pid

    def message_loop(self):
        # intended to run in a background thread, handling each message as received
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

            # republish external pubsub events on local pypubsub bus, plus
            # give any registered listeners chance to see the message too
            if event.msg_type == "PUBSUB":
                for cb in self._on_pubsub:
                    cb(event)

            # exception raised in worker
            elif event.msg_type == "FATAL":
                self.ctx.log(logging.INFO, f"Fatal Event received: {event.msg}")
                self._on_fatal(event)

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
            raise ValueError(f"Could not send run message to process {process_id}")

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
                msg_src=str(process_id),
                msg_type="PUBSUB",
                msg=dict(
                    topic="procedure.lifecycle.statechange",
                    kwargs=dict(new_state=final_state),
                ),
            )
            self.ctx.event_queue.put(msg)

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

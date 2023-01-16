"""
The ska_oso_oet.procedure.application module holds classes and functionality that
belong in the application layer of the OET. This layer holds the application
interface, delegating to objects in the domain layer for business rules and
actions.
"""
import collections
import dataclasses
import enum
import itertools
import logging
import multiprocessing.context
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from pubsub import pub
from ska_db_oda.unit_of_work.restunitofwork import RESTUnitOfWork
from ska_oso_pdm.entities.common import procedures as pdm_procedures
from ska_oso_pdm.entities.common.sb_definition import SBDefinition

from ska_oso_oet import mptools
from ska_oso_oet.event import topics

from .. import domain
from ..domain import EventMessage, ProcedureState

base_dir = os.path.dirname(os.path.realpath(__file__))
ABORT_SCRIPT = domain.FileSystemScript("file://" + base_dir + "/abort.py")

HISTORY_MAX_LENGTH = 10

DELETEABLE_STATES = [
    domain.ProcedureState.COMPLETE,
    domain.ProcedureState.FAILED,
    domain.ProcedureState.STOPPED,
    domain.ProcedureState.UNKNOWN,
]

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class PrepareProcessCommand:
    """
    PrepareProcessCommand is input argument dataclass for the
    ScriptExecutionService prepare command. It holds all the information
    required to load and prepare a Python script ready for execution.
    """

    script: domain.ExecutableScript
    init_args: domain.ProcedureInput


@dataclasses.dataclass
class StartProcessCommand:
    """
    StartProcessCommand is the input argument dataclass for the
    ScriptExecutionService start command. It holds the references required to
    start a prepared script process along with any late-binding runtime
    arguments the script may require.
    """

    process_uid: int
    fn_name: str
    run_args: domain.ProcedureInput
    force_start: bool = False


@dataclasses.dataclass
class StopProcessCommand:
    """
    StopProcessCommand is the input argument dataclass for the
    ScriptExecutionService Stop command. It holds the references required to
    Stop a script process along with any late-binding runtime
    arguments the script may require.
    """

    process_uid: int
    run_abort: bool


@dataclasses.dataclass
class ProcedureHistory:
    """
    ProcedureHistory is a non-functional dataclass holding execution history of
    a Procedure spanning all transactions.

    process_states: records time for each change of ProcedureState (list of
        tuples where tuple contains the ProcedureState and time when state was
        changed to)
    stacktrace: None unless execution_error is True in which case stores
        stacktrace from process
    """

    def __init__(
        self,
        process_states: Optional[List[Tuple[domain.ProcedureState, float]]] = None,
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


@dataclasses.dataclass
class ArgCapture:
    """
    ArgCapture is a struct to record function call and time of invocation.
    """

    fn: str
    fn_args: domain.ProcedureInput
    time: float = None


@dataclasses.dataclass
class ActivityCommand:
    """ """

    activity_name: str
    sbd_id: str
    prepare_only: bool
    create_env: bool
    script_args: Dict[str, domain.ProcedureInput]


class ActivityState(enum.Enum):
    REQUESTED = enum.auto()


@dataclasses.dataclass
class ProcedureSummary:
    """
    ProcedureSummary is a brief representation of a runtime Procedure. It
    captures essential information required to describe a Procedure and to
    distinguish it from other Procedures.
    """

    id: int  # pylint: disable=invalid-name
    script: domain.ExecutableScript
    script_args: List[ArgCapture]
    history: ProcedureHistory
    state: domain.ProcedureState


@dataclasses.dataclass
class ActivitySummary:
    id: int  # pylint: disable=invalid-name
    pid: int
    sbd_id: str
    activity_name: str
    prepare_only: bool
    script_args: Dict[str, domain.ProcedureInput]
    activity_states: List[Tuple[ActivityState, float]]


@dataclasses.dataclass
class Activity:
    activity_id: int
    procedure_id: Optional[int]
    sbd_id: str
    activity_name: str
    prepare_only: bool


class ScriptExecutionService:
    """
    ScriptExecutionService provides the high-level interface and facade for
    the script execution domain (i.e., the 'procedure' domain).

    The interface is used to load and run Python scripts in their own
    independent Python child process.

    The shutdown method should be called to ensure cleanup of any
    multiprocessing artefacts owned by this service.
    """

    # defines which lifecycle event to announce when a lifecycle.statechange is received
    # TODO rationalise procedure lifecycle events and topics for multi-run scripts
    state_to_topic = {
        ProcedureState.RUNNING: topics.procedure.lifecycle.started,
        ProcedureState.COMPLETE: topics.procedure.lifecycle.complete,
        ProcedureState.FAILED: topics.procedure.lifecycle.failed,
        ProcedureState.STOPPED: topics.procedure.lifecycle.stopped,
    }

    def __init__(
        self,
        mp_context: Optional[multiprocessing.context.BaseContext] = None,
        abort_script: domain.ExecutableScript = ABORT_SCRIPT,
        on_pubsub: Optional[List[Callable[[EventMessage], None]]] = None,
    ):
        """
        Create a new ScriptExecutionService.

        The .stop() method of this ScriptExecutionService can run a second
        script once the current process has been terminated. By default, this
        second script calls SubArrayNode.abort() to halt further activities
        on the sub-array controlled by the terminated script. To run a
        different script, define the script URI in the abort_script_uri
        argument to this constructor.

        :param mp_context: multiprocessing context to use or None for default
        :param abort_script: post-termination script for two-phase abort
        :param on_pubsub: callbacks to call when PUBSUB message is received
        """
        callbacks = [self._update_state, self._update_stacktrace]
        if on_pubsub:
            callbacks.extend(on_pubsub)

        self._process_manager = domain.ProcessManager(mp_context, callbacks)
        self._abort_script = abort_script

        self.states: Dict[int, domain.ProcedureState] = {}
        self.script_args: Dict[int, List[ArgCapture]] = {}
        self.scripts: Dict[int, domain.ExecutableScript] = {}
        self.history: Dict[int, ProcedureHistory] = collections.defaultdict(
            ProcedureHistory
        )

        self._state_updating = threading.RLock()
        # pub.subscribe(self._update_state, topics.procedure.lifecycle.statechange)
        # pub.subscribe(self._update_stacktrace, topics.procedure.lifecycle.stacktrace)

    def prepare(self, cmd: PrepareProcessCommand) -> ProcedureSummary:
        """
        Load and prepare a Python script for execution, but do not commence
        execution.

        :param cmd: dataclass argument capturing the script identity and load
            arguments
        :return:
        """
        pid = self._process_manager.create(cmd.script, init_args=cmd.init_args)

        # this needs to be set here as create() will return before the ScriptWorker
        # process has emitted CREATING event. Receipt of the CREATING event will
        # set this state to CREATING again.
        self.states[pid] = ProcedureState.CREATING

        now = time.time()
        self.scripts[pid] = cmd.script
        self.script_args[pid] = [ArgCapture(fn="init", fn_args=cmd.init_args, time=now)]

        self._prune_old_state()

        return self._summarise(pid)

    def start(self, cmd: StartProcessCommand) -> ProcedureSummary:
        """
        Start execution of a prepared procedure.

        :param cmd: dataclass argument capturing the execution arguments
        :return:
        """
        self._process_manager.run(
            cmd.process_uid,
            call=cmd.fn_name,
            run_args=cmd.run_args,
            force_start=cmd.force_start,
        )
        self.script_args[cmd.process_uid].append(
            ArgCapture(fn=cmd.fn_name, fn_args=cmd.run_args, time=time.time())
        )
        return self._summarise(cmd.process_uid)

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

    def stop(self, cmd: StopProcessCommand) -> List[ProcedureSummary]:
        """
        Stop execution of a running procedure, optionally running a
        second script once the first process has terminated.

        :param cmd: dataclass argument capturing the execution arguments
        :return:
        """
        self._process_manager.stop(cmd.process_uid)

        # exit early if not instructed to run post-termination script
        if not cmd.run_abort:
            # Did not start a new process so return empty list
            return []

        # abort requires a subarray to target
        subarray_id = self._get_subarray_id(cmd.process_uid)

        # prepare second script
        prepare_cmd = PrepareProcessCommand(
            script=self._abort_script,
            init_args=domain.ProcedureInput(subarray_id=subarray_id),
        )
        procedure_summary = self.prepare(prepare_cmd)

        # wait for the script to be READY, then run it
        self._wait_for_state(procedure_summary.id, ProcedureState.READY)

        # start the second script
        run_cmd = StartProcessCommand(
            process_uid=procedure_summary.id,
            fn_name="main",
            run_args=domain.ProcedureInput(),
        )
        summary = self.start(run_cmd)
        return [summary]

    def shutdown(self):
        self._process_manager.shutdown()

    def _get_subarray_id(self, pid: int) -> int:
        """
        Return a Subarray id for given procedure ID.

        :param pid: Procedure ID to summarise
        :return: subarray id
        """
        procedure_summary = self._summarise(pid)
        subarray_ids = {
            arg_capture.fn_args.kwargs["subarray_id"]
            for arg_capture in procedure_summary.script_args
            if "subarray_id" in arg_capture.fn_args.kwargs
        }
        if not subarray_ids:
            raise ValueError("Subarray ID not specified")
        if len(subarray_ids) > 1:
            raise ValueError("Multiple subarray IDs found")
        return subarray_ids.pop()

    def _summarise(self, pid: int) -> ProcedureSummary:
        """
        Return a ProcedureSummary for the Procedure with the given ID.

        CAUTION: do NOT modify the arguments! SES state is exposed here.

        :param pid: Procedure ID to summarise
        :return: ProcedureSummary
        """
        with self._state_updating:
            state = self.states[pid]
            script = self.scripts[pid]
            script_args = self.script_args[pid]
            history = self.history[pid]
            return ProcedureSummary(
                id=pid,
                script=script,
                script_args=script_args,
                history=history,
                state=state,
            )

    def _prune_old_state(self):
        """
        Remove the state associated with the oldest deletable Procedures so
        that the state history remains below the history limit
        HISTORY_MAX_LENGTH.
        """
        # Delete oldest deletable procedure if procedure limit reached
        with self._state_updating:
            if len(self.states) > HISTORY_MAX_LENGTH:
                lower_bound = len(self.states) - HISTORY_MAX_LENGTH
                pids_to_consider = list(self.states.keys())[:lower_bound]
                to_delete = {
                    old_pid
                    for old_pid in pids_to_consider
                    if self.states.get(old_pid, None) in DELETEABLE_STATES
                }

                for old_pid in to_delete:
                    del self.states[old_pid]
                    del self.history[old_pid]
                    del self.script_args[old_pid]
                    del self.scripts[old_pid]

    def _update_state(self, event: EventMessage) -> None:
        """
        Callback method that updates Procedure history whenever a message on
        the procedure.lifecycle.statechange topic is received.

        :param event: EventMessage to process
        """
        payload = event.msg
        if payload.get("topic", None) != "procedure.lifecycle.statechange":
            return
        pid = int(event.msg_src)
        new_state = payload["kwargs"]["new_state"]

        now = time.time()
        with self._state_updating:
            previous = self.states.get(pid, None)
            self.states[pid] = new_state
            self.history[pid].process_states.append((new_state, now))

        # publish a legacy lifecycle status change event when appropriate
        if new_state in self.state_to_topic:
            pub.sendMessage(
                self.state_to_topic[new_state],
                msg_src=pid,
                request_id=None,
                result=self._summarise(pid),
            )

        # special case: there's no unique state to signify loading complete
        if previous == ProcedureState.LOADING and new_state == ProcedureState.IDLE:
            pub.sendMessage(
                topics.procedure.lifecycle.created,
                msg_src=pid,
                request_id=None,
                result=self._summarise(pid),
            )

    def _update_stacktrace(self, event: EventMessage) -> None:
        """
        Callback method to record stacktrace event in the Procedure history
        whenever a message on procedure.lifecycle.stacktrace is received.

        :param event: EventMessage to process
        """
        payload = event.msg
        if payload.get("topic", None) != "procedure.lifecycle.stacktrace":
            return
        pid = int(event.msg_src)

        with self._state_updating:
            self.history[pid].stacktrace = event.msg["kwargs"]["stacktrace"]

    def _wait_for_state(self, pid: int, state: ProcedureState, timeout=1.0, tick=0.01):
        """
        A time-bound wait for a Procedure to reach the requested state.

        :param pid: ID of Procedure to wait for
        :param timeout: wait timeout, in seconds
        :param tick: time between state checks, in seconds
        """
        deadline = time.time() + timeout
        sleep_secs = tick
        while self.states.get(pid, None) != state and sleep_secs > 0:
            time.sleep(sleep_secs)
            sleep_secs = mptools._sleep_secs(  # pylint: disable=protected-access
                tick, deadline
            )


class ActivityService:
    """
    ActivityService provides the high-level interface and facade for
    the activity domain.

    The interface is used to run activities referenced by Scheduling Blocks.
    Each activity will run a script (or `procedure`) but ActivityService
    will create the necessary commands for Procedure domain to create
    and execute the scripts.
    """

    def __init__(
        self,
    ):
        # ActivityService does not have state history updates implemented yet so we store a list of
        # states for each activity where the latest state in the list is the current state
        self.states: Dict[int, List[Tuple[ActivityState, int]]] = {}
        self.script_args: Dict[int, Dict[str, domain.ProcedureInput]] = {}
        self.activities: Dict[int, Activity] = {}
        # We need to store this state as the service needs to check if a procedure that has been created
        # is the result of an activity request
        self.request_ids_to_aid: Dict[int, int] = {}

        # counter used to generate activity ID for new activities
        self._aid_counter = itertools.count(1)

        self._oda = RESTUnitOfWork()

    def prepare_run_activity(self, cmd: ActivityCommand, request_id: int) -> None:
        """
        Prepare to run the activity of a Scheduling Block. This includes retrieving the script
        from the scheduling block and sending the request messages to the
        ScriptExecutionService to prepare the script.

        The request_id is required to be propagated through the messages sent to the Procedure layer,
        so the REST layer can wait for the correct response event.

        :param cmd: dataclass argument capturing the activity name and SB ID
        :param request_id: The original request_id from the REST layer
        """

        aid = next(self._aid_counter)
        with self._oda:
            sbd: SBDefinition = self._oda.sbds.get(cmd.sbd_id)

        pdm_script = sbd.activities.get(cmd.activity_name)

        script = self._get_oet_script(pdm_script, cmd.create_env)
        script_args = self._get_script_args(pdm_script, cmd)
        prepare_cmd = PrepareProcessCommand(
            script=script,
            init_args=script_args.get("init", domain.ProcedureInput()),
        )
        pub.sendMessage(
            topics.request.procedure.create,
            # The message needs to appear to come from the worker layer in order for the republish logic
            # to send it out to the main queue
            msg_src="ActivityServiceWorker",
            request_id=request_id,
            cmd=prepare_cmd,
        )

        # This should be the first state to be added so create a new list
        self.states[aid] = [(ActivityState.REQUESTED, request_id)]

        # The Activity dataclass is an internal representation of the Activity. The procedure_id will be populated
        # once the procedure created event has been received
        self.activities[aid] = Activity(
            activity_id=aid,
            procedure_id=None,
            activity_name=cmd.activity_name,
            sbd_id=cmd.sbd_id,
            prepare_only=cmd.prepare_only,
        )
        self.script_args[aid] = script_args
        self.request_ids_to_aid[request_id] = aid

    def complete_run_activity(
        self, prepared_summary: ProcedureSummary, request_id: int
    ) -> Optional[ActivitySummary]:
        """
        Complete the request to run the Activity, using the ProcedureSummary that is now available.
        This includes updating the Activity with the procedure_id, sending the request to start the procedure if prepare_only is not set to True,
        and returning the ActivitySummary.

        :param prepared_summary: the ProcedureSummary for the Procedure related to the requested Activity
        :param request_id: The original request_id from the REST layer

        """
        try:
            aid = self.request_ids_to_aid[request_id]
        except KeyError:
            # The request_id does not match a request sent to the activity domain, so the procedure is not linked to an activity
            return None

        activity = self.activities[aid]
        # Now the ProcedureSummary is available, update the Activity with the procedure_id
        activity.procedure_id = prepared_summary.id

        if not activity.prepare_only:
            #  TODO: should we allow here for multiple functions or limit to just main as is assumed by PM?
            fns_to_start = [fn for fn in self.script_args[aid].keys() if fn != "init"]
            for fn in fns_to_start:
                start_cmd = StartProcessCommand(
                    prepared_summary.id,
                    fn_name=fn,
                    run_args=self.script_args[aid][fn],
                    force_start=True,
                )
                pub.sendMessage(
                    topics.request.procedure.start,
                    msg_src="ActivityServiceWorker",
                    request_id=request_id,
                    cmd=start_cmd,
                )

        return self._summarise(aid)

    def summarise(
        self, activity_ids: Optional[List[int]] = None
    ) -> List[ActivitySummary]:
        """
        Return ActivitySummary objects for Activities with the requested IDs.

        This method accepts an optional list of integers, representing the
        Activity IDs to summarise. If the IDs are left undefined,
        ActivitySummary objects for all current Activities will be returned.

        :param activity_ids: optional list of Activity IDs to summarise.
        :return: list of ActivitySummary objects
        """
        all_activity_ids = self.states.keys()
        if activity_ids is None:
            activity_ids = all_activity_ids

        missing_pids = {p for p in activity_ids if p not in all_activity_ids}
        if missing_pids:
            raise ValueError(f"Activity IDs not found: {missing_pids}")

        return [self._summarise(activity_id) for activity_id in activity_ids]

    def _summarise(self, aid: int) -> ActivitySummary:
        """
        Return a ActivitySummary for the Activity with the given ID.

        :param aid: Activity ID to summarise
        :return: ActivitySummary
        """
        state = self.states[aid]
        activity = self.activities[aid]
        script_args = self.script_args[aid]
        return ActivitySummary(
            id=aid,
            pid=activity.procedure_id,
            activity_name=activity.activity_name,
            sbd_id=activity.sbd_id,
            script_args=script_args,
            activity_states=state,
            prepare_only=activity.prepare_only,
        )

    def _get_oet_script(
        self, pdm_script: pdm_procedures.PythonProcedure, create_env: bool
    ) -> domain.ExecutableScript:
        """
        Converts the PDM representation of the script retrieved from the SB into the OET representation.
        """
        if isinstance(pdm_script, pdm_procedures.FilesystemScript):
            return domain.FileSystemScript(script_uri=pdm_script.path)
        elif isinstance(pdm_script, pdm_procedures.GitScript):
            git_args = domain.GitArgs(
                git_repo=pdm_script.repo, git_branch=pdm_script.branch
            )
            return domain.GitScript(
                script_uri=pdm_script.path, git_args=git_args, create_env=create_env
            )
        else:
            raise RuntimeError(
                f"Cannot run script with type {pdm_script.__class__.__name__}"
            )

    def _get_script_args(
        self, pdm_script: pdm_procedures.PythonProcedure, cmd: ActivityCommand
    ) -> dict[str, domain.ProcedureInput]:
        """
        Combines the function args from the SB with any overwrites sent in the command,
        returning a dict of the OET representation of the args for each function.
        """
        script_args = {}
        for fn in pdm_script.function_args:
            script_args[fn] = domain.ProcedureInput(
                *pdm_script.function_args[fn].args,
                **pdm_script.function_args[fn].kwargs,
            )

        script_args.update(cmd.script_args)
        return script_args

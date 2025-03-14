"""
The ska_oso_oet.procedure.application module holds classes and functionality that
belong in the application layer of the OET. This layer holds the application
interface, delegating to objects in the domain layer for business rules and
actions.
"""
import collections
import dataclasses
import logging
import multiprocessing.context
import os
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from pubsub import pub
from pydantic import BaseModel

from ska_oso_oet import mptools
from ska_oso_oet.event import topics
from ska_oso_oet.procedure import domain
from ska_oso_oet.procedure.domain import EventMessage, ProcedureState

base_dir = os.getenv("SCRIPTS_LOCATION", "/scripts")
ABORT_SCRIPT = domain.FileSystemScript(str("file://" + base_dir + "/abort.py"))

HISTORY_MAX_LENGTH = 10

DELETEABLE_STATES = [
    domain.ProcedureState.COMPLETE,
    domain.ProcedureState.FAILED,
    domain.ProcedureState.STOPPED,
    domain.ProcedureState.UNKNOWN,
]

LOGGER = logging.getLogger(__name__)


class PrepareProcessCommand(BaseModel):
    """
    PrepareProcessCommand is input argument dataclass for the
    ScriptExecutionService prepare command. It holds all the information
    required to load and prepare a Python script ready for execution.
    """

    script: domain.ExecutableScript
    init_args: domain.ProcedureInput

    def __init__(
        self, script: domain.ExecutableScript, init_args: domain.ProcedureInput
    ):
        super(PrepareProcessCommand, self).__init__(script=script, init_args=init_args)


class StartProcessCommand(BaseModel):
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

    def __init__(
        self,
        process_uid: int,
        fn_name: str,
        run_args: domain.ProcedureInput,
        force_start: bool = False,
    ):
        super(StartProcessCommand, self).__init__(
            process_uid=process_uid,
            fn_name=fn_name,
            run_args=run_args,
            force_start=force_start,
        )


class StopProcessCommand(BaseModel):
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


class ArgCapture(BaseModel):
    """
    ArgCapture is a struct to record function call and time of invocation.
    """

    fn: str
    fn_args: domain.ProcedureInput
    time: float = None


class ProcedureSummary(BaseModel):
    """
    ProcedureSummary is a brief representation of a runtime Procedure. It
    captures essential information required to describe a Procedure and to
    distinguish it from other Procedures.
    """

    id: int  # pylint: disable=invalid-name
    script: domain.ExecutableScript | None
    script_args: List[ArgCapture] | None
    history: ProcedureHistory | None
    state: domain.ProcedureState | None

    def __init__(
        self,
        id: int,
        script: domain.ExecutableScript | None,
        script_args: List[ArgCapture] | None,
        history: ProcedureHistory | None,
        state: domain.ProcedureState | None,
    ):
        super(ProcedureSummary, self).__init__(
            id=id,
            script=script,
            script_args=script_args,
            history=history,
            state=state,
        )


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
        ProcedureState.INITIALISING: topics.procedure.lifecycle.started,
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

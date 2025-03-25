# pylint: disable=protected-access, unused-import
# - protected-access - tests need to access protected props
# - unused-import - test fixtures imported from test_domain
"""
Unit tests for the ska_oso_oet.procedure.application module.
"""
import multiprocessing
import time
import unittest.mock as mock
import uuid
from unittest.mock import MagicMock, call, patch

import pubsub.pub
import pytest

from ska_oso_oet.event import topics
from ska_oso_oet.mptools import EventMessage
from ska_oso_oet.procedure.application import (
    ArgCapture,
    PrepareProcessCommand,
    ProcedureHistory,
    ProcedureSummary,
    ScriptExecutionService,
    StartProcessCommand,
    StopProcessCommand,
)
from ska_oso_oet.procedure.domain import (
    FileSystemScript,
    ProcedureInput,
    ProcedureState,
    ProcessManager,
)

# disable F401 to stop flake8 complaining about unused fixture imports
from tests.unit.ska_oso_oet.procedure.test_domain import (  # noqa: F401
    fixture_abort_script,
    fixture_fail_script,
    fixture_init_hang_script,
    fixture_main_hang_script,
    fixture_script,
)

from .test_ui import PubSubHelper


@pytest.fixture(name="sleep_script")
def fixture_sleep_script(tmpdir):
    """
    Pytest fixture to return a path to a script that sleeps a user-defined
    amount of time.
    """
    script_path = tmpdir.join("sleep_script.py")
    script_path.write(
        """
import time

def init(subarray_id):
    pass

def main(secs):
    time.sleep(secs)
"""
    )
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="ses")
def fixture_ses():
    """
    Pytest fixture to return a ScriptExecutionService with automatic cleanup.
    """
    pubsub.pub.unsubAll()
    ses = ScriptExecutionService()
    yield ses
    ses.shutdown()


class TestProcedureHistory:
    def test_procedure_history_default_values_are_as_expected(self):
        """
        Verify that ProcedureHistory default values are set as
        expected if not provided.
        """
        procedure_history = ProcedureHistory()
        assert procedure_history.process_states == []
        assert procedure_history.stacktrace is None

    def test_procedure_history_eq(self):
        """
        Verify ProcedureHistory equality
        """
        ph1 = ProcedureHistory()
        ph2 = ProcedureHistory()
        ph3 = ProcedureHistory([(ProcedureState.IDLE, 1601053634.9669704)])
        assert ph1 == ph2
        assert ph1 != ph3
        assert ph1 != object()


class TestScriptExecutionService:
    def test_callback_is_invoked_when_pubsub_message_received(self):
        """
        Confirm that a callback function sees pubsub messages received by the
        SES's ProcessManager.
        """
        non_pubsub_msg = EventMessage("TEST", "foo", "bar")
        pubsub_msg = EventMessage(
            "EXTERNAL COMPONENT",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )

        ses = None
        cb_received = []
        cb_called = multiprocessing.Event()

        def cb(event):
            cb_received.append(event)
            cb_called.set()

        try:
            ses = ScriptExecutionService(on_pubsub=[cb])
            ses._process_manager.ctx.event_queue.put(non_pubsub_msg)
            ses._process_manager.ctx.event_queue.put(pubsub_msg)
            ses._process_manager.ctx.event_queue.put(non_pubsub_msg)
            cb_called.wait(0.1)

        finally:
            if ses is not None:
                ses.shutdown()

        assert cb_called.is_set()
        assert len(cb_received) == 1
        # can't do direct eq comparison as queue item is pickled copy, hence
        # object ID is different
        received: EventMessage = cb_received.pop()
        assert received.id == pubsub_msg.id and received.msg == pubsub_msg.msg

    def test_ses_calls_process_manager_as_expected(
        self, ses: ScriptExecutionService, main_hang_script
    ):
        """
        Verify ScriptExecutionService interactions with ProcessManager for
        standard script execution.
        """
        mgr = mock.Mock(wraps=ses._process_manager)
        ses._process_manager = mgr

        main_running = multiprocessing.Barrier(2)
        prepare_cmd = PrepareProcessCommand(
            script=main_hang_script, init_args=ProcedureInput(main_running)
        )
        summary = ses.prepare(prepare_cmd)
        pid = summary.id
        mgr.create.assert_called_once_with(
            prepare_cmd.script, init_args=prepare_cmd.init_args
        )

        ses._wait_for_state(pid, ProcedureState.READY)
        run_cmd = StartProcessCommand(
            process_uid=pid, fn_name="main", run_args=ProcedureInput()
        )
        _ = ses.start(run_cmd)
        mgr.run.assert_called_once_with(
            run_cmd.process_uid,
            call=run_cmd.fn_name,
            run_args=run_cmd.run_args,
            force_start=False,
        )

        ses._wait_for_state(pid, ProcedureState.RUNNING)
        main_running.wait(0.1)
        stop_cmd = StopProcessCommand(process_uid=pid, run_abort=False)
        _ = ses.stop(stop_cmd)
        mgr.stop.assert_called_once_with(stop_cmd.process_uid)

        # assert no other calls to ProcessManager
        assert len(mgr.method_calls) == 3

    def test_two_phase_abort_calls_process_manager_as_expected(
        self, sleep_script, script
    ):
        """
        Verify ScriptExecutionService interactions with ProcessManager when
        terminating a script with a request to run the follow-on abort script
        """
        pubsub.pub.unsubAll()
        # fixture accepts any positional args and kwargs, which is useful as the
        # subarray ID will be passed to the abort script
        ses = ScriptExecutionService(abort_script=script)
        subarray_id = 3
        try:
            prepare_cmd = PrepareProcessCommand(
                script=sleep_script, init_args=ProcedureInput(subarray_id=subarray_id)
            )
            summary = ses.prepare(prepare_cmd)
            pid = summary.id

            ses._wait_for_state(pid, ProcedureState.READY)
            run_cmd = StartProcessCommand(
                process_uid=pid,
                fn_name="main",
                run_args=ProcedureInput(
                    2
                ),  # max 2 seconds before process completes naturally
            )
            _ = ses.start(run_cmd)
            ses._wait_for_state(pid, ProcedureState.RUNNING)

            # wrap the manager here so that we only capture calls related to stop
            mgr = mock.Mock(wraps=ses._process_manager)
            ses._process_manager = mgr

            stop_cmd = StopProcessCommand(process_uid=pid, run_abort=True)
            _ = ses.stop(stop_cmd)

            assert len(mgr.method_calls) == 3
            mgr.stop.assert_called_once_with(1)
            mgr.create.assert_called_once_with(
                script, init_args=ProcedureInput(subarray_id=subarray_id)
            )
            mgr.run.assert_called_once_with(
                pid + 1, call="main", run_args=ProcedureInput(), force_start=False
            )

        finally:
            ses.shutdown()

    def test_happy_path_events(self, ses, script):
        """
        Verify that OET events are published at the appropriate times for
        happy-path script execution.
        """
        helper = PubSubHelper()

        prepare_cmd = PrepareProcessCommand(script=script, init_args=ProcedureInput())
        summary = ses.prepare(prepare_cmd)

        helper.wait_for_message_on_topic(topics.procedure.lifecycle.created)
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0

        run_cmd = StartProcessCommand(
            process_uid=summary.id, fn_name="main", run_args=ProcedureInput()
        )
        _ = ses.start(run_cmd)

        helper.wait_for_message_on_topic(topics.procedure.lifecycle.complete)
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0

        filtered = [
            t for t in helper.topic_list if t != topics.procedure.lifecycle.statechange
        ]
        assert filtered == [
            topics.procedure.lifecycle.created,
            topics.procedure.lifecycle.started,
            topics.procedure.lifecycle.complete,
        ]

    def test_sad_path_events(self, ses, fail_script):
        """
        Verify that OET events are published at the appropriate times for a
        script that raises an exception.
        """
        helper = PubSubHelper()

        prepare_cmd = PrepareProcessCommand(
            script=fail_script, init_args=ProcedureInput()
        )
        summary = ses.prepare(prepare_cmd)

        helper.wait_for_message_on_topic(
            topics.procedure.lifecycle.created, timeout=3.0
        )
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0

        run_cmd = StartProcessCommand(
            process_uid=summary.id, fn_name="main", run_args=ProcedureInput(msg="foo")
        )
        _ = ses.start(run_cmd)

        helper.wait_for_message_on_topic(
            topics.procedure.lifecycle.stacktrace, timeout=3.0
        )
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0

        filtered = [
            t for t in helper.topic_list if t != topics.procedure.lifecycle.statechange
        ]
        assert filtered == [
            topics.procedure.lifecycle.created,
            topics.procedure.lifecycle.started,
            topics.procedure.lifecycle.failed,
            topics.procedure.lifecycle.stacktrace,
        ]

    def test_stop_events(self, ses, init_hang_script):
        """
        Verify the behaviour of SES.stop(), confirming that OET events are published
        at the appropriate times when a script is terminated.
        """
        helper = PubSubHelper()

        init_running = multiprocessing.Barrier(2)
        prepare_cmd = PrepareProcessCommand(
            script=init_hang_script, init_args=ProcedureInput(init_running)
        )
        summary = ses.prepare(prepare_cmd)
        pid = summary.id
        ses._wait_for_state(pid, ProcedureState.IDLE)

        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0

        init_running.wait(0.1)
        ses._wait_for_state(pid, ProcedureState.READY)

        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0

        stop_cmd = StopProcessCommand(process_uid=pid, run_abort=False)
        _ = ses.stop(stop_cmd)
        ses._wait_for_state(pid, ProcedureState.STOPPED)

        assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.complete)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
        assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 1

        filtered = [
            t for t in helper.topic_list if t != topics.procedure.lifecycle.statechange
        ]
        assert filtered == [
            topics.procedure.lifecycle.created,
            topics.procedure.lifecycle.started,
            topics.procedure.lifecycle.stopped,
        ]

    def test_summarise_with_no_procedures(self, ses):
        assert ses.summarise() == []

    def test_summarise_returns_specific_summary(self, ses):
        ses.states = {
            10: ProcedureState.COMPLETE,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }

        with patch.object(ScriptExecutionService, "_summarise") as method:
            _ = ses.summarise([20])
            method.assert_called_once_with(20)

    def test_summarise_returns_all_summaries_when_no_pid_requested(self, ses):
        ses.states = {
            10: ProcedureState.COMPLETE,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }

        expected = [1, 2, 3]
        with patch.object(ScriptExecutionService, "_summarise") as method:
            method.side_effect = expected

            actual = ses.summarise()
            assert actual == expected
            method.assert_has_calls(
                [call(pid) for pid in ses.states.keys()], any_order=True
            )

    def test_summarise_fails_when_invalid_pid_requested(self, ses):
        ses.states = {
            10: ProcedureState.COMPLETE,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }

        with pytest.raises(ValueError):
            ses.summarise([10, 11, 30])

    def test_scalar_summarise(self, ses, script):  # pylint: disable=protected-access
        """
        Verify that the private _summarise method compiles the execution
        history correctly.

        Note that this test exercises the SES and ProcessManager, hence this
        also functions as an integration test between the two.
        """
        t = 12345
        init_args = ProcedureInput(1, 2, a="b", c="d")
        run_args = ProcedureInput(3, 4, e="f", g="h")
        history = ProcedureHistory(
            [
                (ProcedureState.CREATING, t),
                (ProcedureState.IDLE, t),
                (ProcedureState.LOADING, t),
                (ProcedureState.IDLE, t),
                (ProcedureState.READY, t),
                (ProcedureState.RUNNING, t),
                (ProcedureState.READY, t),
                (ProcedureState.COMPLETE, t),
            ],
            stacktrace=None,
        )

        prepare_cmd = PrepareProcessCommand(script, init_args=init_args)
        with patch("time.time", MagicMock(return_value=t)):
            summary = ses.prepare(prepare_cmd)
            pid = summary.id
            ses._wait_for_state(pid, ProcedureState.READY)

            run_cmd = StartProcessCommand(
                process_uid=pid, fn_name="main", run_args=run_args
            )
            ses.start(run_cmd)
            ses._wait_for_state(pid, ProcedureState.COMPLETE)

        expected = ProcedureSummary(
            id=pid,
            script=script,
            script_args=[
                ArgCapture(fn="init", fn_args=init_args, time=t),
                ArgCapture(fn="main", fn_args=run_args, time=t),
            ],
            history=history,
            state=ProcedureState.COMPLETE,
        )

        summary = ses._summarise(pid)
        assert summary == expected

    def test_scalar_summarise_raises_exception_on_invalid_input(self, ses):
        with pytest.raises(KeyError):
            ses._summarise(9999)

    def test_ses_get_subarray_id_for_requested_pid(self, ses):
        """
        Verify that the private method _get_subarray_id returns
        subarray id correctly
        """
        subarray_id = 123
        process_pid = 456

        init_args = ArgCapture(
            fn="init", fn_args=ProcedureInput(subarray_id=subarray_id), time=1
        )
        process_summary = ProcedureSummary(
            id=process_pid,
            script=FileSystemScript(script_uri="file://a"),
            script_args=[init_args],
            history=ProcedureHistory(),
            state=ProcedureState.IDLE,
        )
        expected = [process_summary]

        with patch.object(
            ScriptExecutionService, "_summarise", return_value=process_summary
        ) as method:
            returned = ses._get_subarray_id(process_pid)

            assert method.called_with(process_pid)
            assert returned == expected[0].script_args[0].fn_args.kwargs["subarray_id"]

    def test_ses_get_subarray_id_fails_on_missing_subarray_id(self, ses):
        """
        Verify that an exception is raised when subarray ID is missing for requested
        PID
        """
        init_args = ArgCapture(fn="init", fn_args=ProcedureInput(), time=1)
        process_summary = ProcedureSummary(
            id=1,
            script=FileSystemScript(script_uri="file://a"),
            script_args=[init_args],
            history=ProcedureHistory(),
            state=ProcedureState.IDLE,
        )

        with patch.object(
            ScriptExecutionService, "_summarise", return_value=process_summary
        ):
            with pytest.raises(ValueError):
                ses._get_subarray_id(1)  # pylint: disable=protected-access


class TestSESHistory:
    def test_init_args_are_captured_in_history(self, ses):
        """
        Verify that arguments to prepare() are captured and stored.
        """
        script = FileSystemScript(script_uri="file://test.py")
        init_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
        now = time.time()
        pid = 567

        # sending this command...
        cmd = PrepareProcessCommand(script=script, init_args=init_args)
        # ... should record this in the script_args
        expected = ArgCapture(fn="init", fn_args=init_args, time=now)

        with patch("time.time", MagicMock(return_value=now)):
            with patch.object(ProcessManager, "create", return_value=pid):
                with patch.object(ScriptExecutionService, "_summarise"):
                    _ = ses.prepare(cmd)

        assert len(ses.script_args[pid]) == 1
        assert ses.script_args[pid] == [expected]

    def test_run_args_are_captured_in_history(self, ses):
        """
        Verify that arguments to start() are captured and stored
        """
        timestamp = 12345
        pid = 456
        fn_name = "foo"
        run_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")

        # must create process for history entries to be present
        script = FileSystemScript(script_uri="file://test.py")
        cmd = PrepareProcessCommand(script=script, init_args=ProcedureInput())
        with patch.object(ProcessManager, "create", return_value=pid):
            with patch.object(ScriptExecutionService, "_summarise"):
                _ = ses.prepare(cmd)

        # now we can test when method invocation args are recorded
        cmd = StartProcessCommand(pid, fn_name=fn_name, run_args=run_args)
        expected = ArgCapture(fn=fn_name, fn_args=run_args, time=timestamp)

        with patch("time.time", MagicMock(return_value=timestamp)):
            with patch.object(ScriptExecutionService, "_summarise"):
                with patch.object(ProcessManager, "run"):
                    _ = ses.start(cmd)

        assert len(ses.script_args[pid]) == 2
        assert ses.script_args[pid][1] == expected

    def test_failure_and_stacktrace_recorded_in_history(
        self, ses: ScriptExecutionService, fail_script
    ):
        t = 12345
        random_exc_string = str(uuid.uuid4())
        init_args = ProcedureInput()
        run_args = ProcedureInput(random_exc_string)
        expected_states = [
            (ProcedureState.CREATING, t),  # ScriptWorker initialising
            (ProcedureState.IDLE, t),  # ScriptWorker ready
            (ProcedureState.LOADING, t),  # load user module
            (ProcedureState.IDLE, t),  # user module loaded
            # fail script has no init so no IDLE->READY expected
            (ProcedureState.READY, t),  # init complete
            (ProcedureState.RUNNING, t),  # main running
            (ProcedureState.FAILED, t),  # exception raised
        ]

        with patch("time.time", MagicMock(return_value=t)):
            prepare_cmd = PrepareProcessCommand(script=fail_script, init_args=init_args)
            summary = ses.prepare(prepare_cmd)

            pid = summary.id
            ses._wait_for_state(pid, ProcedureState.READY)

            assert summary.history.stacktrace is None

            cmd = StartProcessCommand(
                process_uid=pid, fn_name="main", run_args=run_args
            )
            _ = ses.start(cmd)
            ses._wait_for_state(pid, ProcedureState.FAILED)

            time.sleep(1.0)
            summary = ses._summarise(pid)

        assert summary.history.process_states == expected_states

        # most recent stacktrace should also have been captured and recorded in history
        assert random_exc_string in summary.history.stacktrace

    def test_exceeding_history_limit_removes_oldest_deletable_state(self, ses, script):
        """
        Verify that SES removes the oldest deletable state and history when
        the record limit is reached.
        """
        prepare_cmd = PrepareProcessCommand(script=script, init_args=ProcedureInput())

        # reduce max history to make test quicker
        limit = 3
        with patch(
            "ska_oso_oet.procedure.application.HISTORY_MAX_LENGTH",
            new=limit,
        ):
            for _ in range(limit):
                summary = ses.prepare(prepare_cmd)
                pid = summary.id
                ses._wait_for_state(pid, ProcedureState.READY)
                run_cmd = StartProcessCommand(
                    process_uid=pid, fn_name="main", run_args=ProcedureInput()
                )
                summary = ses.start(run_cmd)
                pid = summary.id

            ses._wait_for_state(pid, ProcedureState.COMPLETE)
            assert len(ses.history) == limit
            assert len(ses.script_args) == limit
            assert len(ses.states) == limit
            assert len(ses.scripts) == limit

            oldest_pid = next(iter(ses.states.keys()))
            assert oldest_pid in ses.history
            assert oldest_pid in ses.script_args
            assert oldest_pid in ses.states
            assert oldest_pid in ses.scripts

            _ = ses.prepare(prepare_cmd)

        # adding procedure should not increase the number of procedures
        # and should remove the oldest procedure
        assert len(ses.history) == limit
        assert oldest_pid not in ses.history
        assert oldest_pid not in ses.script_args
        assert oldest_pid not in ses.states
        assert oldest_pid not in ses.scripts

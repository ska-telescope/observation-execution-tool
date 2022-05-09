# pylint: disable=W0613
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the ska_oso_oet.procedure.domain module.
"""
import importlib.machinery
import multiprocessing
import time
from multiprocessing import Manager
from typing import List
from unittest.mock import MagicMock, patch

import pubsub.pub
import pytest

import ska_oso_oet.mptools as mptools
from ska_oso_oet.event import topics
from ska_oso_oet.mptools import EventMessage, MPQueue
from ska_oso_oet.procedure.domain import (
    FileSystemScript,
    GitArgs,
    GitScript,
    ModuleFactory,
    ProcedureInput,
    ProcedureState,
    ProcessManager,
    ScriptWorker,
)
from tests.unit.ska_oso_oet.mptools.test_mptools import _proc_worker_wrapper_helper
from tests.unit.ska_oso_oet.procedure.application.test_restserver import PubSubHelper

multiprocessing_contexts = [
    multiprocessing.get_context("spawn"),
    multiprocessing.get_context("fork"),
    multiprocessing.get_context("forkserver"),
]


@pytest.fixture
def script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def pubsub_script(tmpdir):
    """
    Pytest fixture to return a path to a script that emits OET events
    """
    script_path = tmpdir.join("script.py")
    script_path.write(
        """
import threading
from pubsub import pub
from ska_oso_oet.event import topics

def main(msg):
    pub.sendMessage(
        topics.user.script.announce,
        msg_src=threading.current_thread().name,
        msg=msg
    )
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def barrier_script(tmpdir):
    """
    Pytest fixture to return a path to a script that sets an event
    """
    script_path = tmpdir.join("script.py")
    script_path.write(
        """
INIT_RUNNING = None
MAIN_RUNNING = None
RESUME = None

def init(evt1, evt2, evt3):
    global INIT_RUNNING, MAIN_RUNNING, RESUME
    INIT_RUNNING, MAIN_RUNNING, RESUME = evt1, evt2, evt3

    INIT_RUNNING.wait()
    RESUME.wait()

def main():
    MAIN_RUNNING.wait()
    RESUME.wait()
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def init_hang_script(tmpdir):
    """
    Pytest fixture to return a path to a script that sets an event
    """
    script_path = tmpdir.join("script.py")
    script_path.write(
        """
def init(init_running):
    init_running.wait()
    while True:
        pass
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def main_hang_script(tmpdir):
    """
    Pytest fixture to return a path to a script that sets an event
    """
    script_path = tmpdir.join("script.py")
    script_path.write(
        """
MAIN_RUNNING = None

def init(main_running):
    global MAIN_RUNNING
    MAIN_RUNNING = main_running

def main():
    MAIN_RUNNING.wait()
    while True:
        pass
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def fail_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("fail.py")
    script_path.write(
        """
def main(msg):
    raise Exception(msg)
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def abort_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("abort.py")
    script_path.write(
        """
import time

Q = None
MAIN_RUNNING = None

def init(q, running):
    global Q, MAIN_RUNNING
    Q, MAIN_RUNNING = q, running

def main():
    MAIN_RUNNING.wait()
    time.sleep(2)
    Q.put('foo')
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def script_that_increments_and_returns_scan_id(tmpdir):
    """
    Pytest fixture to return a path to a script with main() that increments
    the scan ID and adds the value to a queue.
    """
    path = tmpdir.join("script_for_scan_id.py")

    path.write(
        """
from ska_oso_oet.command import SCAN_ID_GENERATOR

Q = None

def init(q):
    global Q
    Q = q

def main():
    Q.put(SCAN_ID_GENERATOR.next())
"""
    )
    return FileSystemScript(f"file://{str(path)}")


@pytest.fixture
def manager():
    """
    Pytest fixture to return a prepared ProcessManager
    """
    mgr = ProcessManager()
    yield mgr
    mgr.shutdown()
    pubsub.pub.unsubAll()


class TestExecutableScript:
    def test_filesystem_script_object_creation(self):
        script = FileSystemScript("file://script.py")
        assert isinstance(script, FileSystemScript)
        assert script.script_uri == "file://script.py"

    def test_git_script_object_creation(self):
        script = GitScript("git://script.py", git_args=GitArgs())
        assert isinstance(script, GitScript)
        assert script.script_uri == "git://script.py"
        assert script.git_args == GitArgs()
        assert script.default_git_env is True

    def test_filesystem_script_raises_error_on_incorrect_prefix(self):
        with pytest.raises(ValueError) as e:
            _ = FileSystemScript("incorrectprefix://script.py")
        assert (
            "Incorrect prefix for FileSystemScript: incorrectprefix://script.py"
            in str(e)
        )

    def test_git_script_raises_error_on_incorrect_prefix(self):
        with pytest.raises(ValueError) as e:
            _ = GitScript("incorrectprefix://script.py", git_args=GitArgs())
        assert "Incorrect prefix for GitScript: incorrectprefix://script.py" in str(e)


class TestGitArgs:
    def test_git_args_input_accepts_expected_values(self):
        """
        Verify that GitArgs arguments.
        """
        git_args = GitArgs(
            git_repo="git://test.com", git_branch="master", git_commit="HEAD"
        )
        assert git_args.git_repo == "git://test.com"
        assert git_args.git_commit == "HEAD"

    def test_git_args_input_eq_works_as_expected(self):
        """
        Verify GitArgs equality
        """
        ga1 = GitArgs("git://test.com", "HEAD", "master")
        ga2 = GitArgs("git://test.com", "HEAD", "master")
        ga3 = GitArgs("test")
        assert ga1 == ga2
        assert ga1 != ga3
        assert ga1 != object()

    def test_git_args_default_values_are_as_expected(self):
        """
        Verify that GitArgs default values are set as
        expected if not provided.
        """
        git_args = GitArgs()
        assert (
            git_args.git_repo
            == "https://gitlab.com/ska-telescope/ska-oso-scripting.git"
        )
        assert git_args.git_branch == "master"
        assert git_args.git_commit is None


class TestProcedureInput:
    def test_procedure_input_accepts_expected_constructor_values(self):
        """
        Verify that ProcedureInput arguments are slurped into positional and
        keyword/value attributes.
        """
        procedure_input = ProcedureInput(1, 2, 3, a=1, b=2)
        assert procedure_input.args == (1, 2, 3)
        assert procedure_input.kwargs == dict(a=1, b=2)

    def test_procedure_input_equality(self):
        """
        Verify ProcedureInput equality
        """
        pi1 = ProcedureInput(1, 2, 3, a=1, b=2)
        pi2 = ProcedureInput(1, 2, 3, a=1, b=2)
        pi3 = ProcedureInput(4, a=1)
        assert pi1 == pi2
        assert pi1 != pi3
        assert pi1 != object()


def wait_for_empty_message_queue(
    manager, timeout=1.0, tick=0.01
):  # pylint: disable=protected-access
    # primitive way to wait for all ScriptWorker messages to be
    # handled. Adds a message to the queue then waits a maximum
    # of timeout seconds for the queue size to become zero again
    # junk_msg = EventMessage('test', 'foo', 'bar')
    # assert manager.ctx.event_queue.safe_put(junk_msg) is True
    deadline = time.time() + timeout
    sleep_secs = tick
    while (not manager.ctx.event_queue.empty()) and sleep_secs > 0:
        time.sleep(sleep_secs)
        sleep_secs = mptools._sleep_secs(tick, deadline)


def wait_for_state(
    manager: ProcessManager, pid: int, state: ProcedureState, timeout=1.0, tick=0.01
):  # pylint: disable=protected-access
    deadline = time.time() + timeout
    sleep_secs = tick
    while manager.states.get(pid, None) != state and sleep_secs > 0:
        time.sleep(sleep_secs)
        sleep_secs = mptools._sleep_secs(tick, deadline)


class TestScriptWorkerPubSub:
    @pytest.mark.parametrize("mp", multiprocessing_contexts)
    def test_external_messages_are_published_locally(self, mp, caplog):
        """
        Verify that message event is published if the event originates from an
        external source.
        """
        work_q = MPQueue(ctx=mp)
        msg = EventMessage(
            "EXTERNAL COMPONENT",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )
        work_q.put(msg)
        _proc_worker_wrapper_helper(
            mp, caplog, ScriptWorker, args=(work_q,), expect_shutdown_evt=True
        )

        # there's no easy way to assert that the external event was republished
        # on an an independent pypubsub bus. Workaround is to assert that the
        # republishing code was run via the log message
        assert "Republishing external event: EXTERNAL COMPONENT" in caplog.text

    @pytest.mark.parametrize("mp", multiprocessing_contexts)
    def test_internal_messages_not_republished(self, mp, caplog):
        """
        Verify that message event is not published if the event originates from
        an internal source.
        """
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp)
        # TEST is the default component name assigned in
        # _proc_worker_wrapper_helper. This message should not be published to pypubsub
        msg = EventMessage(
            "TEST",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )
        work_q.put(msg)

        _proc_worker_wrapper_helper(
            mp, caplog, ScriptWorker, args=(work_q,), expect_shutdown_evt=True
        )

        msgs_on_topic = helper.messages_on_topic(topics.request.procedure.list)
        assert len(msgs_on_topic) == 0


class TestProcessManagerScriptWorkerIntegration:
    @staticmethod
    def assert_states(helper: PubSubHelper, pid: int, expected: List[ProcedureState]):
        msgs = helper.messages_on_topic(topics.procedure.lifecycle.statechange)
        states = [msg["new_state"] for msg in msgs if int(msg["msg_src"]) == pid]
        assert states == expected

    def test_happy_path_script_execution_lifecycle_states(
        self, manager: ProcessManager, barrier_script
    ):
        """
        Verify that a new ScriptWorker sends the appropriate lifecycle states.

        The mptools ProcWorker tests already verify that events are set at the
        appropriate times. This test is to confirm that lifecycle EventMessages
        are sent at the appropriate times too.
        """
        helper = PubSubHelper()

        init_running = multiprocessing.Barrier(2)
        main_running = multiprocessing.Barrier(2)
        resume = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running, main_running, resume)

        pid = manager.create(barrier_script, init_args=init_args)
        init_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        expected = [
            ProcedureState.CREATING,  # ScriptWorker initialising
            ProcedureState.IDLE,  # ScriptWorker ready
            ProcedureState.LOADING,  # load user module
            ProcedureState.IDLE,  # user module loaded
            ProcedureState.RUNNING,  # init present and called
        ]
        self.assert_states(helper, pid, expected)

        # let init complete, then check for completion
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.READY)
        expected.append(ProcedureState.READY)  # init complete
        self.assert_states(helper, pid, expected)

        # now set main running
        manager.run(pid, call="main", run_args=ProcedureInput())
        expected.append(ProcedureState.RUNNING)  # main running
        main_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        self.assert_states(helper, pid, expected)

        # wait for ScriptWorker process to complete
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.COMPLETE)
        expected.extend(
            [
                ProcedureState.READY,  # main complete
                ProcedureState.COMPLETE,  # script complete
            ]
        )
        self.assert_states(helper, pid, expected)

    def test_error_in_main_lifecycles_states(
        self, manager: ProcessManager, fail_script
    ):
        helper = PubSubHelper()

        pid = manager.create(fail_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)

        manager.run(pid, call="main", run_args=ProcedureInput("foo"))

        wait_for_state(manager, pid, ProcedureState.FAILED)
        expected = [
            ProcedureState.CREATING,  # ScriptWorker initialising
            ProcedureState.IDLE,  # ScriptWorker ready
            ProcedureState.LOADING,  # load user module
            ProcedureState.IDLE,  # user module loaded
            # fail script has no init so no IDLE->READY expected
            ProcedureState.READY,  # init complete
            ProcedureState.RUNNING,  # main running
            ProcedureState.FAILED,  # exception raised
        ]
        helper.wait_for_lifecycle(ProcedureState.FAILED)
        # wait_for_state(manager, pid, ProcedureState.FAILED)
        # helper.wait_for_message_on_topic(topics.procedure.lifecycle.stacktrace)
        self.assert_states(helper, pid, expected)

    # @patch('ska_oso_oet.mptools.Proc.STARTUP_WAIT_SECS', new=300)
    def test_stop_during_init_sets_lifecycle_state_to_stopped(
        self, manager, init_hang_script
    ):
        """
        Verify that procedure terminate changes to STOPPED
        when terminate() is called
        """
        helper = PubSubHelper()

        init_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running)

        pid = manager.create(init_hang_script, init_args=init_args)

        init_running.wait(0.1)
        wait_for_empty_message_queue(manager)
        manager.stop(pid)

        expected = [
            ProcedureState.CREATING,  # ScriptWorker initialising
            ProcedureState.IDLE,  # ScriptWorker ready
            ProcedureState.LOADING,  # load user module
            ProcedureState.IDLE,  # user module loaded
            ProcedureState.RUNNING,  # init running
            ProcedureState.STOPPED,  # init stopped
        ]
        helper.wait_for_lifecycle(ProcedureState.STOPPED)
        self.assert_states(helper, pid, expected)

    def test_stop_during_main_sets_lifecycle_state_to_stopped(
        self, manager, main_hang_script
    ):
        """
        Verify that procedure state changes to STOPPED
        when terminate() is called
        """
        helper = PubSubHelper()

        main_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(main_running)

        pid = manager.create(main_hang_script, init_args=init_args)
        helper.wait_for_lifecycle(ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        main_running.wait(0.5)

        helper.wait_for_lifecycle(ProcedureState.RUNNING)
        manager.stop(pid)
        helper.wait_for_lifecycle(ProcedureState.STOPPED)

        expected = [
            ProcedureState.CREATING,  # ScriptWorker initialising
            ProcedureState.IDLE,  # ScriptWorker ready
            ProcedureState.LOADING,  # load user module
            ProcedureState.IDLE,  # user module loaded
            ProcedureState.RUNNING,  # init running
            ProcedureState.READY,  # init complete
            ProcedureState.RUNNING,  # main running
            ProcedureState.STOPPED,  # main stopped
        ]
        self.assert_states(helper, pid, expected)

    def test_running_set_to_none_on_stop(self, manager, init_hang_script):
        """
        Verify that ProcessManager sets running procedure attribute to None
        when script is stopped
        """
        init_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running)

        pid = manager.create(init_hang_script, init_args=init_args)
        init_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        assert manager.running is not None

        manager.stop(pid)
        wait_for_state(manager, pid, ProcedureState.STOPPED)
        assert manager.running is None

    def test_running_to_none_when_process_completes(self, manager, barrier_script):
        """
        Verify that ProcessManager sets running procedure attribute to None
        when process completes.
        """
        init_running = multiprocessing.Barrier(2)
        main_running = multiprocessing.Barrier(2)
        resume = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running, main_running, resume)

        pid = manager.create(barrier_script, init_args=init_args)
        init_running.wait(0.1)
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.READY)

        # now set main running
        manager.run(pid, call="main", run_args=ProcedureInput())
        main_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        assert manager.running is not None

        resume.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.COMPLETE)
        assert manager.running is None

    # def test_happy_path_procedure_lifecycle_events(self, manager, script):
    #     """
    #     Verify that OET events are published at the appropriate times for a
    #     happy-path script.
    #     """
    #     helper = PubSubHelper()
    #
    #     pid = manager.create(script, init_args=ProcedureInput())
    #     helper.wait_for_message_on_topic(topics.procedure.lifecycle.created)
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 0
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
    #
    #     manager.run(pid, call="main", run_args=ProcedureInput())
    #     helper.wait_for_message_on_topic(topics.procedure.lifecycle.stopped)
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 1
    #     assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
    #
    #     assert helper.topic_list == [
    #         topics.procedure.lifecycle.created,
    #         topics.procedure.lifecycle.started,
    #         topics.procedure.lifecycle.stopped,
    #     ]
    #
    #     def test_sad_path_procedure_lifecycle_events(self, manager, fail_script):
    #         """
    #         Verify that OET events are published at the appropriate times for a
    #         sad-path script.
    #         """
    #         helper = PubSubHelper()
    #
    #         pid = manager.create(fail_script, init_args=ProcedureInput())
    #         helper.wait_for_message_on_topic(topics.procedure.lifecycle.created)
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 0
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 0
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 0
    #
    #         manager.run(pid, call="main", run_args=ProcedureInput(msg="foo"))
    #         helper.wait_for_message_on_topic(topics.procedure.lifecycle.failed)
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.created)) == 1
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.started)) == 1
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.failed)) == 1
    #         assert len(helper.messages_on_topic(topics.procedure.lifecycle.stopped)) == 1
    #
    #         assert helper.topic_list == [
    #             topics.procedure.lifecycle.created,
    #             topics.procedure.lifecycle.started,
    #             topics.procedure.lifecycle.stopped,
    #             topics.procedure.lifecycle.failed,
    #         ]
    #
    def test_events_emitted_from_scripts_are_republished(self, manager, pubsub_script):
        """
        Verify that OET events are published at the appropriate times for a
        sad-path script.
        """
        helper = PubSubHelper()

        pid = manager.create(pubsub_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)

        manager.run(pid, call="main", run_args=ProcedureInput(msg="foo"))
        helper.wait_for_message_on_topic(topics.user.script.announce)
        user_msgs = helper.messages_on_topic(topics.user.script.announce)
        assert len(user_msgs) == 1


class TestProcessManager:
    def test_running_is_none_on_a_new_process_manager(self, manager):
        """
        Verify that a new ProcessManager has no running procedure
        """
        assert manager.running is None

    def test_no_procedures_on_a_new_process_manager(self, manager):
        """
        Verify that a new ProcessManager has no procedures
        """
        assert not manager.procedures

    def test_create_adds_to_procedures(self, manager, script):
        """
        Verify that ProcessManager.procedures references the processes it creates
        """
        for _ in range(3):
            len_before = len(manager.procedures)
            pid = manager.create(script, init_args=ProcedureInput())
            assert len(manager.procedures) == len_before + 1
            assert pid in manager.procedures

    def test_cleanup_on_completed(self, manager, script):
        pid = manager.create(script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.COMPLETE)

        # TODO how can we synchronise with the cleanup function running in another thread?
        time.sleep(0.1)
        assert pid not in manager.states
        assert pid not in manager.script_queues
        assert pid not in manager.procedures

    def test_cleanup_on_stopped(self, manager, init_hang_script):
        init_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running)

        pid = manager.create(init_hang_script, init_args=init_args)
        init_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        manager.stop(pid)
        wait_for_state(manager, pid, ProcedureState.STOPPED)

        # TODO how can we synchronise with the cleanup function running in another thread?
        time.sleep(0.1)
        assert pid not in manager.states
        assert pid not in manager.script_queues
        assert pid not in manager.procedures

    def test_cleanup_on_failed(self, manager, fail_script):
        pid = manager.create(fail_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput("foo"))
        wait_for_state(manager, pid, ProcedureState.FAILED)

        # TODO how can we synchronise with the cleanup function running in another thread?
        time.sleep(0.1)
        assert pid not in manager.states
        assert pid not in manager.script_queues
        assert pid not in manager.procedures

    def test_run_sends_run_message(self, manager):
        """
        Verify that a call to ProcessManager.run() sends the run message to the
        ScriptWorker.
        """
        q = manager.ctx.MPQueue()
        manager.procedures[1] = MagicMock()
        manager.states[1] = ProcedureState.READY
        manager.script_queues[1] = q
        method = "foo"
        run_args = ProcedureInput("a", "b", kw1="c", kw2="d")

        manager.run(1, call=method, run_args=run_args)
        msg = q.safe_get(timeout=0.1)
        assert msg.msg_type == "RUN"
        assert msg.msg == (method, run_args)

    def test_run_fails_for_loading_process(self, manager, script):
        """
        Verify that an exception is raised if requesting run() for a procedure
        that has not been loaded or is still loading
        """
        with patch("ska_oso_oet.procedure.domain.ModuleFactory.get_module") as fn:
            fn.side_effect = lambda _: time.sleep(3)
            pid = manager.create(script, init_args=ProcedureInput())
            wait_for_state(manager, pid, ProcedureState.LOADING)

            assert manager.states[pid] == ProcedureState.LOADING
            with pytest.raises(ValueError):
                manager.run(pid, call="main", run_args=ProcedureInput())

    def test_run_fails_for_running_process(self, manager, barrier_script):
        """
        Verify that an exception is raised when requesting run() for a procedure
        that is already running
        """
        init_running = multiprocessing.Barrier(2)
        main_running = multiprocessing.Barrier(2)
        resume = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running, main_running, resume)

        pid = manager.create(barrier_script, init_args=init_args)
        init_running.wait(0.1)
        resume.wait()
        resume.reset()

        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        main_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        with pytest.raises(ValueError):
            manager.run(pid, call="main", run_args=ProcedureInput())
        resume.wait()

    def test_stop_fails_on_invalid_pid(self, manager):
        """
        Verify that an exception is raised when stop() is requested for an invalid
        PID
        """
        with pytest.raises(ValueError):
            manager.stop(321)

    def test_run_fails_on_invalid_pid(self, manager):
        """
        Verify that an exception is raised when run() is requested for an invalid
        PID
        """
        with pytest.raises(ValueError):
            manager.run(321, call="foo", run_args=ProcedureInput())

    def test_stop_fails_on_process_that_is_not_running(self, manager, script):
        """
        Verify that an exception is raised when requesting stop() for a procedure
        that is not running
        """
        pid = manager.create(script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.COMPLETE)
        with pytest.raises(ValueError):
            manager.stop(pid)

    def test_stop_terminates_the_process(self, manager, abort_script):
        """
        Verify that ProcessManager stops a script execution
        """
        helper = PubSubHelper()
        with Manager() as mgr:
            q = mgr.Queue()
            is_running = multiprocessing.Barrier(2)
            pid = manager.create(abort_script, init_args=ProcedureInput(q, is_running))
            wait_for_state(manager, pid, ProcedureState.READY)
            manager.run(pid, call="main", run_args=ProcedureInput())

            is_running.wait(0.1)
            helper.wait_for_lifecycle(ProcedureState.RUNNING)
            manager.stop(pid)
            helper.wait_for_lifecycle(ProcedureState.STOPPED)
            assert manager.running is None
            assert q.empty()

    def test_callback_sees_received_pubsub_messages(self):
        """
        Callbacks passed to ProcessManager constructor should be given each
        MPTools message received.
        """
        non_pubsub_msg = EventMessage("TEST", "foo", "bar")
        pubsub_msg = EventMessage(
            "EXTERNAL COMPONENT",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )

        cb_received = []
        cb_called = multiprocessing.Event()

        def cb(event):
            cb_received.append(event)
            cb_called.set()

        manager = None
        try:
            manager = ProcessManager(on_pubsub=[cb])
            manager.ctx.event_queue.put(non_pubsub_msg)
            manager.ctx.event_queue.put(pubsub_msg)
            manager.ctx.event_queue.put(non_pubsub_msg)
            cb_called.wait(0.1)
        finally:
            if manager is not None:
                manager.shutdown()

        assert cb_called.is_set()
        assert len(cb_received) == 1
        # can't do direct eq comparison as queue item is pickled copy, hence
        # object ID is different
        received: EventMessage = cb_received.pop()
        assert received.id == pubsub_msg.id and received.msg == pubsub_msg.msg


class TestModuleFactory:
    @patch.object(ModuleFactory, "_load_module_from_git")
    def test_get_module_calls_git_load_function(self, mock_git_load):
        mock_git_load.side_effect = [MagicMock(importlib.machinery.SourceFileLoader)]

        git_script = GitScript("git://test/script.py", GitArgs())
        _ = ModuleFactory.get_module(git_script)
        mock_git_load.assert_called_once_with(git_script)

    @patch.object(ModuleFactory, "_load_module_from_file")
    def test_get_module_calls_file_load_function(self, mock_file_load):
        mock_file_load.side_effect = [MagicMock(importlib.machinery.SourceFileLoader)]

        file_script = FileSystemScript("file://test/script.py")
        _ = ModuleFactory.get_module(file_script)
        mock_file_load.assert_called_once_with(file_script.script_uri)


def test_scan_id_persists_between_executions(
    manager,
    script_that_increments_and_returns_scan_id,
):
    """
    The scan ID should be shared and persisted between process executions.
    """
    queue = multiprocessing.Queue()
    init_args = ProcedureInput(queue)

    def run_script():
        pid = manager.create(
            script=script_that_increments_and_returns_scan_id,
            init_args=init_args,
        )
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.COMPLETE)

    run_script()
    scan_id = queue.get(timeout=1)

    run_script()
    next_scan_id = queue.get(timeout=1)

    assert next_scan_id == scan_id + 1

# pylint: disable=W0613
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the ska_oso_oet.procedure.domain module.
"""
import multiprocessing
import operator
import time
import uuid
from multiprocessing import Manager
from typing import List
from unittest.mock import MagicMock, call, patch

import pytest

import ska_oso_oet.mptools as mptools
from ska_oso_oet.procedure.domain import (
    HISTORY_MAX_LENGTH,
    ArgCapture,
    FileSystemScript,
    GitArgs,
    GitScript,
    ProcedureHistory,
    ProcedureInput,
    ProcedureState,
    ProcedureSummary,
    ProcessManager,
)


@pytest.fixture
def script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
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
    with mgr.ctx:
        yield mgr


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


class TestProcessManagerScriptWorkerIntegration:
    @staticmethod
    def assert_states(history: ProcedureHistory, expected: List[ProcedureState]):
        states = [
            state
            for state, _ in sorted(history.process_states, key=operator.itemgetter(1))
        ]
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
        history = manager.history[pid]
        self.assert_states(history, expected)

        # let init complete, then check for completion
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.READY)
        expected.append(ProcedureState.READY)  # init complete
        self.assert_states(history, expected)

        # now set main running
        manager.run(pid, call="main", run_args=ProcedureInput())
        expected.append(ProcedureState.RUNNING)  # main running
        main_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        self.assert_states(history, expected)

        # wait for ScriptWorker process to complete
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.COMPLETED)
        expected.extend(
            [
                ProcedureState.READY,  # main complete
                ProcedureState.COMPLETED,  # script complete
            ]
        )
        self.assert_states(history, expected)

    def test_error_in_main_lifecycles_states(
        self, manager: ProcessManager, fail_script
    ):
        pid = manager.create(fail_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        history = manager.history[pid]

        assert history.stacktrace is None
        random_exc_string = str(uuid.uuid4())
        manager.run(pid, call="main", run_args=ProcedureInput(random_exc_string))

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
        self.assert_states(history, expected)

        # most recent stacktrace should also have been captured and recorded in history
        assert random_exc_string in history.stacktrace

    # @patch('ska_oso_oet.mptools.Proc.STARTUP_WAIT_SECS', new=300)
    def test_stop_during_init_sets_lifecycle_state_to_stopped(
        self, manager, init_hang_script
    ):
        """
        Verify that procedure terminate changes to STOPPED
        when terminate() is called
        """
        init_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running)

        pid = manager.create(init_hang_script, init_args=init_args)
        history = manager.history[pid]

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
        wait_for_empty_message_queue(manager)
        self.assert_states(history, expected)

    def test_stop_during_main_sets_lifecycle_state_to_stopped(
        self, manager, main_hang_script
    ):
        """
        Verify that procedure terminate changes to STOPPED
        when terminate() is called
        """
        main_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(main_running)

        pid = manager.create(main_hang_script, init_args=init_args)
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        main_running.wait(0.5)

        history = manager.history[pid]
        wait_for_empty_message_queue(manager)
        manager.stop(pid)

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
        wait_for_empty_message_queue(manager)
        self.assert_states(history, expected)

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
        wait_for_state(manager, pid, ProcedureState.COMPLETED)
        assert manager.running is None


# REDUNDANT
# def test_creation_of_a_new_procedure_is_added_to_history(procedure):
#     """
#     Verify that the CREATED state and time are recorded in procedure's history
#     """
#     assert ProcedureState.IDLE in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.IDLE], float)


# REDUNDANT
# def test_procedure_start_sets_state_to_running(procedure):
#     """
#     Verify that procedure state changes to RUNNING when run() is called
#     """
#     procedure.start()
#     assert procedure.state == ProcedureState.RUNNING

# redundant - covered in happy path tests
# def test_procedure_run_executes_user_script(script_with_queue_path):
#     """
#     Verify that user script executes when run() is called
#     """
#     procedure = Procedure(script=script_with_queue_path)
#     queue = multiprocessing.Queue()
#     procedure.script_args["run"].args = [queue, procedure]
#     procedure.run()
#     assert queue.get(timeout=1) is None
#     with pytest.raises(Empty):
#         queue.get(block=False)


#
# def test_runtime_arguments_are_passed_to_user_script(procedure):
#     """
#     Verify that arguments passed from procedure are accessible in the user script
#     """
#     run_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
#     procedure.script_args["run"] = run_args
#     procedure.user_module = MagicMock()
#     procedure.run()
#     procedure.user_module.main.assert_called_with(5, 6, 7, kw3="c", kw4="d")


# Redundant?
# def test_procedure_start_raises_exception_on_a_running_procedure(procedure):
#     """
#     Verify that a RUNNING procedure can not be run again
#     """
#     procedure.start()
#     with pytest.raises(Exception):
#         procedure.start()


# REDUNDANT - fold LOAD error into general exception handling?
# def test_procedure_init_raises_exception_on_script_file_not_found():
#     """
#     Verify that FileNotFoundError is raised if script file does not exist
#     """
#     script = FileSystemScript("file://abcbs")
#
#     with pytest.raises(FileNotFoundError):
#         _ = Procedure(script=script)


# REDUNDANT
# def test_procedure_terminate_sets_state_to_stopped(procedure):
#     """
#     Verify that procedure terminate changes to STOPPED
#     when terminate() is called
#     """
#     procedure.start()
#     procedure.terminate()
#     assert procedure.state == ProcedureState.STOPPED


# REDUNDANT
# def test_procedure_terminate_records_state_in_history(procedure):
#     """
#     Verify that procedure terminate records STOPPED state in the history
#     """
#     procedure.start()
#     procedure.terminate()
#     assert ProcedureState.IDLE in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.IDLE], float)
#     assert ProcedureState.STOPPED in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.STOPPED], float)

# not applicable. Any child process can now be terminated, although utility of stopping an IDLE process is questionable
# def test_procedure_terminate_not_allowed_if_process_is_not_running(procedure):
#     """
#     Verify that procedure raises an exception if process to terminate
#     is not in RUNNING state
#     """
#     with pytest.raises(Exception):
#         procedure.terminate()


class TestProcessManager:
    def test_summarise_with_no_procedures(self, manager):
        assert manager.summarise() == []

    def test_summarise_returns_specific_summary(self, manager):
        fake_states = {
            10: ProcedureState.COMPLETED,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }
        manager.states = fake_states

        with patch.object(ProcessManager, "_summarise") as method:
            _ = manager.summarise([20])
            method.assert_called_once_with(20)

    def test_summarise_returns_all_summaries_when_no_pid_requested(self, manager):
        fake_states = {
            10: ProcedureState.COMPLETED,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }
        manager.states = fake_states

        expected = [1, 2, 3]
        with patch.object(ProcessManager, "_summarise") as method:
            method.side_effect = expected

            actual = manager.summarise()
            assert actual == expected
            method.assert_has_calls(
                [call(pid) for pid in fake_states.keys()], any_order=True
            )

    def test_summarise_fails_when_invalid_pid_requested(self, manager):
        fake_states = {
            10: ProcedureState.COMPLETED,
            20: ProcedureState.RUNNING,
            30: ProcedureState.IDLE,
        }
        with patch.object(manager, "states", new=fake_states):
            with pytest.raises(ValueError):
                manager.summarise([10, 11, 30])

    def test_private_summarise(
        self, manager, script
    ):  # pylint: disable=protected-access
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
                (ProcedureState.COMPLETED, t),
            ],
            stacktrace=None,
        )

        with patch("time.time", MagicMock(return_value=t)):
            pid = manager.create(script, init_args=init_args)
        wait_for_state(manager, pid, ProcedureState.READY)
        with patch("time.time", MagicMock(return_value=t)):
            manager.run(pid, call="main", run_args=run_args)
        wait_for_state(manager, pid, ProcedureState.COMPLETED)

        expected = ProcedureSummary(
            id=pid,
            script=script,
            script_args=[
                ArgCapture(fn="init", fn_args=init_args, time=t),
                ArgCapture(fn="main", fn_args=run_args, time=t),
            ],
            history=history,
            state=ProcedureState.COMPLETED,
        )

        summary = manager._summarise(pid)
        assert summary == expected

        with pytest.raises(KeyError):
            manager._summarise(9999)

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
        for _ in range(HISTORY_MAX_LENGTH):
            len_before = len(manager.procedures)
            pid = manager.create(script, init_args=ProcedureInput())
            assert len(manager.procedures) == len_before + 1
            assert pid in manager.procedures

    def test_create_removes_oldest_deletable_state(self, manager, script):
        """
        Verify that ProcessManager removes the oldest deletable state when
        the maximum number of saved procedures is reached.
        """
        limit = 3

        with patch("ska_oso_oet.procedure.domain.HISTORY_MAX_LENGTH", new=limit):
            for _ in range(limit):
                pid = manager.create(script, init_args=ProcedureInput())
                wait_for_state(manager, pid, ProcedureState.READY)
                manager.run(pid, call="main", run_args=ProcedureInput())

            wait_for_state(manager, pid, ProcedureState.COMPLETED)
            assert len(manager.history) == limit
            assert len(manager.script_args) == limit
            assert len(manager.states) == limit
            assert len(manager.scripts) == limit

            oldest_pid = next(iter(manager.states.keys()))
            assert oldest_pid in manager.history
            assert oldest_pid in manager.script_args
            assert oldest_pid in manager.states
            assert oldest_pid in manager.scripts

            _ = manager.create(script, init_args=ProcedureInput())

        # adding procedure should not increase the number of procedures
        # and should remove the oldest procedure
        assert len(manager.history) == limit
        assert oldest_pid not in manager.history
        assert oldest_pid not in manager.script_args
        assert oldest_pid not in manager.states
        assert oldest_pid not in manager.scripts

    def test_cleanup_on_completed(self, manager, script):
        pid = manager.create(script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.COMPLETED)

        # TODO how can we synchronise with the cleanup function running in another thread?
        time.sleep(0.1)
        assert manager.states[pid] == ProcedureState.COMPLETED
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
        assert manager.states[pid] == ProcedureState.STOPPED
        assert pid not in manager.script_queues
        assert pid not in manager.procedures

    def test_cleanup_on_failed(self, manager, fail_script):
        pid = manager.create(fail_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput("foo"))
        wait_for_state(manager, pid, ProcedureState.FAILED)

        # TODO how can we synchronise with the cleanup function running in another thread?
        time.sleep(0.1)
        assert manager.states[pid] == ProcedureState.FAILED
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
        manager.script_args[1] = []
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
        wait_for_state(manager, pid, ProcedureState.COMPLETED)
        with pytest.raises(ValueError):
            manager.stop(pid)

    def test_stop_terminates_the_process(self, manager, abort_script):
        """
        Verify that ProcessManager stops a script execution
        """
        with Manager() as mgr:
            q = mgr.Queue()
            is_running = multiprocessing.Barrier(2)
            pid = manager.create(abort_script, init_args=ProcedureInput(q, is_running))
            wait_for_state(manager, pid, ProcedureState.READY)
            manager.run(pid, call="main", run_args=ProcedureInput())

            is_running.wait(0.1)
            wait_for_empty_message_queue(manager)
            manager.stop(pid)

            wait_for_empty_message_queue(manager)
            assert manager.running is None
            assert q.empty()

    def test_init_args_are_captured(self, manager, script):
        """
        Verify that initial arguments to ProcessManager are captured and stored on the
        ProcessManager
        """
        init_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
        expected = ArgCapture(fn="init", fn_args=init_args, time=12345)

        with patch("time.time", MagicMock(return_value=12345)):
            pid = manager.create(script, init_args=init_args)

        assert len(manager.script_args[pid]) == 1
        assert manager.script_args[pid][0] == expected

    def test_run_args_are_captured(self, manager, script):
        """
        Verify that the arguments to ProcessManager run() are captured and stored on the
        procedure instance
        """
        run_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
        expected = ArgCapture(fn="main", fn_args=run_args, time=12345)

        with patch("time.time", MagicMock(return_value=12345)):
            pid = manager.create(script, init_args=ProcedureInput())
            wait_for_state(manager, pid, ProcedureState.READY)
            manager.run(pid, call="main", run_args=run_args)

        assert len(manager.script_args[pid]) == 2
        assert manager.script_args[pid][1] == expected

    # redundant - already have tests that exercise init arg capture, plus this won't work
    # until GitScripts are handled are user module is loaded on worker creation
    # def test_process_manager_create_captures_git_arguments(self, manager, script):
    #     """
    #     Verify that ProcessManager passes through git arguments to the procedures it creates
    #     """
    #     expected = GitArgs(git_repo="http://foo.git", git_commit="HEAD", git_branch="main")
    #     git_script = GitScript(script_uri=script.script_uri, git_args=expected)
    #     pid = manager.create(git_script, init_args=ProcedureInput())
    #     created = manager.procedures[pid]
    #     assert isinstance(created.script, GitScript)
    #     assert created.script.git_args == expected


# REDUNDANT
# def test_process_manager_run_changes_state_of_procedure_to_running(
#     manager, script, process_cleanup
# ):
#     """
#     Verify that procedure state changes when ProcessManager starts
#     procedure execution
#     """
#     pid = manager.create(script, init_args=ProcedureInput())
#     assert manager.procedures[pid].state == ProcedureState.IDLE
#     manager.run(pid, run_args=ProcedureInput())
#     assert manager.procedures[pid].state == ProcedureState.RUNNING


# def test_process_manager_run_sets_running_procedure(manager, tmpdir):
#     """
#     Verify that ProcessManager sets the running procedure attribute
#     appropriately when run() is called
#     """
#     script_path = tmpdir.join("sleep.py")
#     script_path.write(
#         """
# IN_MAIN = None
# SHUTDOWN = None
#
# def init(in_main, shutdown_event):
#     global IN_MAIN, SHUTDOWN
#     IN_MAIN, SHUTDOWN = in_main, shutdown_event
#
# def main():
#     IN_MAIN.set()
#     while not SHUTDOWN.is_set():
#         continue
# """
#     )
#     script = FileSystemScript(f"file://{str(script_path)}")
#
#     in_main_event = multiprocessing.Event()
#     shutdown_event = multiprocessing.Event()
#     pid = manager.create(
#         script, init_args=ProcedureInput(in_main_event, shutdown_event)
#     )
#     manager.run(pid, run_args=ProcedureInput())
#     in_main_event.wait(1.0)
#     assert manager.running == manager.procedures[pid]
#     shutdown_event.set()


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_updates_state_of_completed_procedures(manager, script):
#     """
#     Verify that ProcessManager updates procedure state to COMPLETED when finished
#     successfully
#     """
#     pid = manager.create(script, init_args=ProcedureInput())
#     manager.run(pid, run_args=ProcedureInput())
#     manager.procedures[pid].proc.join(1.0)
#     assert manager.states[pid] == ProcedureState.COMPLETED


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_updates_history_of_completed_procedures(manager, script):
#     """
#     Verify that ProcessManager updates procedure state to COMPLETED when finished
#     successfully
#     """
#     pid = manager.create(script, init_args=ProcedureInput())
#     manager.run(pid, run_args=ProcedureInput())
#     wait_for_process_to_complete(manager)
#     procedure = manager.procedures[pid]
#
#     assert ProcedureState.IDLE in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.IDLE], float)
#     assert ProcedureState.RUNNING in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.RUNNING], float)
#     assert ProcedureState.COMPLETED in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.COMPLETED], float)
#     assert procedure.history.stacktrace is None


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_sets_running_to_none_on_script_failure(manager, fail_script):
#     """
#     Verify that ProcessManager sets running procedure attribute to None
#     when script execution fails
#     """
#     pid = manager.create(fail_script, init_args=ProcedureInput())
#     manager.run(pid, run_args=ProcedureInput())
#     manager.procedures[pid].proc.join(1.0)
#     assert manager.running is None


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_updates_procedure_state_on_script_failure(
#     manager, fail_script
# ):
#     """
#     Verify that ProcessManager removes a failed procedure from
#     the procedures list
#     """
#     pid = manager.create(fail_script, init_args=ProcedureInput())
#     manager.run(pid, run_args=ProcedureInput())
#     wait_for_process_to_complete(manager)
#     assert manager.procedures[pid].state == ProcedureState.FAILED


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_updates_procedure_history_on_script_failure(
#     manager, fail_script
# ):
#     """
#     Verify that ProcessManager updates FAILED to procedure history when script fails
#     """
#     pid = manager.create(fail_script, init_args=ProcedureInput())
#     manager.run(pid, run_args=ProcedureInput())
#     wait_for_process_to_complete(manager)
#     procedure = manager.procedures[pid]
#
#     assert ProcedureState.IDLE in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.IDLE], float)
#     assert ProcedureState.RUNNING in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.RUNNING], float)
#     assert ProcedureState.FAILED in procedure.history.process_states
#     assert isinstance(procedure.history.process_states[ProcedureState.FAILED], float)
#     assert procedure.history.stacktrace is not None


# REDUNDANT - covered in TestProcessManagerScriptWorkerIntegration tests
# def test_process_manager_updates_procedure_state_on_stop(manager, abort_script):
#     """
#     Verify that ProcessManager removes a stopped procedure from
#     the procedures list
#     """
#     with Manager() as mp_mgr:
#         lst = mp_mgr.list()
#         pid = manager.create(abort_script, init_args=ProcedureInput(lst))
#         manager.run(pid, run_args=ProcedureInput(pid))
#         manager.stop(pid)
#         manager.procedures[pid].proc.join(1.0)
#         assert manager.states[pid] == ProcedureState.STOPPED


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
        wait_for_state(manager, pid, ProcedureState.COMPLETED)

    run_script()
    scan_id = queue.get(timeout=1)

    run_script()
    next_scan_id = queue.get(timeout=1)

    assert next_scan_id == scan_id + 1

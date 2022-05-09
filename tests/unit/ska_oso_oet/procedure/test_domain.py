# pylint: disable=W0613
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the ska_oso_oet.procedure.domain module.
"""
import importlib.machinery
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
    GitScript,
    ModuleFactory,
    ProcedureHistory,
    ProcedureInput,
    ProcedureState,
    ProcedureSummary,
    ProcessManager,
)
from ska_oso_oet.procedure.environment import Environment
from ska_oso_oet.procedure.gitmanager import GitArgs


@pytest.fixture
def script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def git_script(tmpdir):
    """
    Pytest fixture to return a path to a git script file
    """
    script_path = tmpdir.join("git_script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return GitScript(
        f"git://{str(script_path)}", git_args=GitArgs(), default_git_env=False
    )


@pytest.fixture
def git_script_branch(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("git_script_branch.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return GitScript(
        f"git://{str(script_path)}",
        git_args=GitArgs(git_branch="git-test-branch"),
        default_git_env=False,
    )


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

    @patch("ska_oso_oet.procedure.domain.GitManager.clone_repo")
    @patch("ska_oso_oet.procedure.domain.subprocess.check_output")
    def test_environment_created_condition_is_set(
        self, mock_subprocess_fn, mock_clone_fn, git_script, manager
    ):
        """
        Verify event is correctly set on Environment object when env is being created.
        """
        environment = Environment(
            "123",
            multiprocessing.Event(),
            multiprocessing.Event(),
            "/",
            "/python/site_packages",
        )
        manager.em.create_env = MagicMock()
        manager.em.create_env.return_value = environment
        # Return path to git file from clone call in env creation and module load
        mock_clone_fn.side_effect = ["", ""]

        pid = manager.create(git_script, init_args=ProcedureInput())
        env = manager.environments[pid]
        assert not env.created.is_set()
        assert env.env_id == environment.env_id

        wait_for_state(manager, pid, ProcedureState.READY, timeout=10)
        assert env.created.is_set()

    @patch("ska_oso_oet.procedure.domain.GitManager.clone_repo")
    @patch("ska_oso_oet.procedure.domain.subprocess.check_output")
    def test_shared_environment_waits_for_creation_to_complete(
        self, mock_subprocess_fn, mock_clone_fn, git_script, git_script_branch, manager
    ):
        """
        Verify calls to subprocess to install environment are only run if the environment does not yet exist.
        In this tests the first two scripts run in the same environment and the third one creates a new environment.
        """
        environment = Environment(
            "123",
            multiprocessing.Event(),
            multiprocessing.Event(),
            "/",
            "/python/site_packages",
        )
        environment2 = Environment(
            "456",
            multiprocessing.Event(),
            multiprocessing.Event(),
            "/",
            "/python/site_packages",
        )
        manager.em.create_env = MagicMock()
        manager.em.create_env.side_effect = [environment, environment, environment2]

        # Return path to git file from clone call in env creation and module load
        mock_clone_fn.return_value = ""
        calls = multiprocessing.Value("i", 0)

        def called(*args, **kwargs):
            calls.value += 1

        mock_subprocess_fn.side_effect = called

        pid1 = manager.create(git_script, init_args=ProcedureInput())
        env1 = manager.environments[pid1]
        pid2 = manager.create(git_script, init_args=ProcedureInput())
        env2 = manager.environments[pid2]

        assert env1 == env2

        wait_for_state(manager, pid1, ProcedureState.READY, timeout=10)
        wait_for_state(manager, pid2, ProcedureState.READY, timeout=10)

        # Subprocess should only be called twice because second script should
        # just wait for first one to create the environment
        assert calls.value == 2

        pid3 = manager.create(git_script_branch, init_args=ProcedureInput())
        env3 = manager.environments[pid3]

        wait_for_state(manager, pid3, ProcedureState.READY, timeout=10)

        assert env1 != env3
        assert env3.created.is_set()

        # Call count should go up because the new script should run in a new environment
        assert calls.value == 4

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

    def test_create_sends_load_and_run_messages_for_filesystemscript(self, manager):
        """
        Verify that a call to ProcessManager.create() sends the load and run init
        messages to ScriptWorker when filesystem script is created.
        """
        manager.ctx.Proc = MagicMock()
        script = FileSystemScript(script_uri="file://test-script.py")
        manager.create(script, init_args=ProcedureInput())
        q = manager.script_queues[1]
        load_msg = q.safe_get()
        run_msg = q.safe_get()
        assert load_msg.msg_type == "LOAD"
        assert load_msg.msg == script
        assert run_msg.msg_type == "RUN"
        assert run_msg.msg == ("init", None)

    def test_create_sends_load_and_run_messages_for_gitscript(self, manager):
        """
        Verify that a call to ProcessManager.create() sends the load and run init
        messages to ScriptWorker when git script is created.
        """
        manager.ctx.Proc = MagicMock()
        git_script = GitScript(script_uri="git://test-script.py", git_args=GitArgs())
        manager.create(git_script, init_args=ProcedureInput())
        q = manager.script_queues[1]
        load_msg = q.safe_get()
        run_msg = q.safe_get()
        assert load_msg.msg_type == "LOAD"
        assert load_msg.msg == git_script
        assert run_msg.msg_type == "RUN"
        assert run_msg.msg == ("init", None)

    def test_create_sends_env_message(self, manager):
        """
        Verify that a call to ProcessManager.create() sends the env message to the
        ScriptWorker when script type is GitScript and default_git_env is False.
        """
        manager.ctx.Proc = MagicMock()
        manager.em.create_env = MagicMock()
        expected_env = Environment("1", None, None, "/", "/site-packages")
        manager.em.create_env.side_effect = [expected_env]
        git_script = GitScript(
            script_uri="git://test-script.py", git_args=GitArgs(), default_git_env=False
        )
        manager.create(git_script, init_args=ProcedureInput())
        q = manager.script_queues[1]
        env_msg = q.safe_get()
        assert env_msg.msg_type == "ENV"
        assert env_msg.msg == git_script

        proc_args = manager.ctx.Proc.call_args
        assert expected_env == proc_args.kwargs["environment"]

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
        wait_for_state(manager, pid, ProcedureState.COMPLETED)

    run_script()
    scan_id = queue.get(timeout=1)

    run_script()
    next_scan_id = queue.get(timeout=1)

    assert next_scan_id == scan_id + 1

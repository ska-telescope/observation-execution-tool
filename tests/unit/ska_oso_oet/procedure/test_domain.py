# pylint: disable=W0613
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the ska_oso_oet.procedure.domain module.
"""
import importlib.machinery
import multiprocessing
import time
from multiprocessing import Manager
from unittest.mock import MagicMock, patch

import pubsub.pub
import pytest
from ska_oso_scripting.event import user_topics

import ska_oso_oet.mptools as mptools
from ska_oso_oet.event import topics
from ska_oso_oet.mptools import EventMessage, MPQueue
from ska_oso_oet.procedure.domain import (
    FileSystemScript,
    GitScript,
    ModuleFactory,
    ProcedureInput,
    ProcedureState,
    ProcessManager,
    ScriptWorker,
)
from ska_oso_oet.procedure.environment import Environment
from ska_oso_oet.procedure.gitmanager import GitArgs
from tests.unit.ska_oso_oet.mptools.test_mptools import _proc_worker_wrapper_helper

from ..test_ui import PubSubHelper

multiprocessing_contexts = [
    multiprocessing.get_context("spawn"),
    multiprocessing.get_context("fork"),
    multiprocessing.get_context("forkserver"),
]


@pytest.fixture(name="script")
def fixture_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="pubsub_script")
def fixture_pubsub_script(tmpdir):
    """
    Pytest fixture to return a path to a script that emits OET events
    """
    script_path = tmpdir.join("script.py")
    script_path.write(
        """
import threading
from pubsub import pub
from ska_oso_scripting.event import user_topics

def main(msg):
    pub.sendMessage(
        user_topics.script.announce,
        msg_src=threading.current_thread().name,
        msg=msg
    )
"""
    )
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="git_script")
def fixture_git_script(tmpdir):
    """
    Pytest fixture to return a path to a git script file
    """
    script_path = tmpdir.join("git_script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return GitScript(
        script_uri=f"git://{str(script_path)}", git_args=GitArgs(), create_env=True
    )


@pytest.fixture(name="git_script_branch")
def fixture_git_script_branch(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("git_script_branch.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return GitScript(
        script_uri=f"git://{str(script_path)}",
        git_args=GitArgs(git_branch="git-test-branch"),
        create_env=True,
    )


@pytest.fixture(name="git_sys_path_script")
def fixture_git_sys_path_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("git_sys_path_script.py")
    script_path.write(
        """
import sys

def main(site_package):
    print(sys.path)
    assert site_package in sys.path
"""
    )
    return GitScript(
        script_uri=f"git://{str(script_path)}", git_args=GitArgs(), create_env=True
    )


@pytest.fixture(name="barrier_script")
def fixture_barrier_script(tmpdir):
    """
    Pytest fixture to return a path to a script that sets an event
    """
    script_path = tmpdir.join("barrier_script.py")
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
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="init_hang_script")
def fixture_init_hang_script(tmpdir):
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
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="main_hang_script")
def fixture_main_hang_script(tmpdir):
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
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="fail_script")
def fixture_fail_script(tmpdir):
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
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="abort_script")
def fixture_abort_script(tmpdir):
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
    return FileSystemScript(script_uri=f"file://{str(script_path)}")


@pytest.fixture(name="manager")
def fixture_manager():
    """
    Pytest fixture to return a prepared ProcessManager
    """
    mgr = ProcessManager()
    yield mgr
    mgr.shutdown()
    pubsub.pub.unsubAll()


class TestExecutableScript:
    def test_filesystem_script_object_creation(self):
        script = FileSystemScript(script_uri="file://script.py")
        assert isinstance(script, FileSystemScript)
        assert script.script_uri == "file://script.py"

    def test_git_script_object_creation(self):
        script = GitScript(script_uri="git://script.py", git_args=GitArgs())
        assert isinstance(script, GitScript)
        assert script.script_uri == "git://script.py"
        assert script.git_args == GitArgs()
        assert script.create_env is False

    def test_filesystem_script_raises_error_on_incorrect_prefix(self):
        with pytest.raises(ValueError) as e:
            _ = FileSystemScript(script_uri="incorrectprefix://script.py")
        assert "Incorrect prefix for FileSystemScript: incorrectprefix://script" in str(
            e
        )

    def test_git_script_raises_error_on_incorrect_prefix(self):
        with pytest.raises(ValueError) as e:
            _ = GitScript(script_uri="incorrectprefix://script.py", git_args=GitArgs())
        assert "Incorrect prefix for GitScript: incorrectprefix://script" in str(e)


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
            == "https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git"
        )
        assert git_args.git_branch == "master"
        assert git_args.git_commit is None

    def test_git_args_branch_not_defaulted_when_commit_given(self):
        """
        Verify that GitArgs if a commit is passed then the branch is not set as default
        if a branch isn't given (as the commit might be from a non main branch)
        """
        git_args = GitArgs(git_commit="qwerty")
        assert (
            git_args.git_repo
            == "https://gitlab.com/ska-telescope/oso/ska-oso-scripting.git"
        )
        assert git_args.git_branch is None
        assert git_args.git_commit == "qwerty"


class TestProcedureInput:
    def test_procedure_input_accepts_expected_constructor_values(self):
        """
        Verify that ProcedureInput arguments are slurped into positional and
        keyword/value attributes.
        """
        procedure_input = ProcedureInput(1, 2, 3, a=1, b=2)
        assert procedure_input.args == [1, 2, 3]
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

    def test_procedure_input_addition(self):
        pi1 = ProcedureInput(1, 2, 3, a=1, b=2)
        pi2 = ProcedureInput(c=3)

        pi3 = pi1 + pi2

        assert pi3.args == [1, 2, 3]
        assert pi3.kwargs == dict(a=1, b=2, c=3)

    def test_procedure_input_addition_overwrite(self):
        pi1 = ProcedureInput(1, 2, 3, a=1, b=2)
        pi2 = ProcedureInput(a=2, c=3)

        pi3 = pi1 + pi2

        assert pi3.args == [1, 2, 3]
        assert pi3.kwargs == dict(a=2, b=2, c=3)

    def test_procedure_input_addition_arg_error(self):
        pi1 = ProcedureInput(1, 2, 3, a=1, b=2)
        pi2 = ProcedureInput(4, a=2, c=3)

        with pytest.raises(NotImplementedError):
            _ = pi1 + pi2


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
        # on an independent pypubsub bus. Workaround is to assert that the
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

    @patch("ska_oso_oet.procedure.domain.ModuleFactory.get_module")
    @pytest.mark.parametrize("mp", multiprocessing_contexts)
    def test_on_load(self, mock_module_fn, mp, caplog):
        """ """
        mock_module_fn.side_effect = MagicMock()
        script = GitScript(script_uri="git://test.py", git_args=GitArgs())
        evt = EventMessage("test", "LOAD", script)

        work_q = MPQueue(ctx=mp)
        work_q.put(evt)

        _proc_worker_wrapper_helper(
            mp, caplog, ScriptWorker, args=(work_q,), expect_shutdown_evt=True
        )
        assert mock_module_fn.called_once_with(script)

    @patch("ska_oso_oet.procedure.domain.ScriptWorker._on_run")
    @patch("ska_oso_oet.procedure.domain.ScriptWorker._on_load")
    @patch("ska_oso_oet.procedure.domain.ScriptWorker._on_env")
    def test_script_worker_calls_correct_function_on_message_type(
        self, mock_env_fn, mock_load_fn, mock_run_fn, caplog
    ):
        mp = multiprocessing.get_context()
        script = GitScript(script_uri="git://test.py", git_args=GitArgs())
        env_evt = EventMessage("test", "ENV", script)
        load_evt = EventMessage("test", "LOAD", script)
        run_evt = EventMessage("test", "RUN", ("init", None))
        work_q = MPQueue(ctx=mp)
        work_q.put(env_evt)
        work_q.put(load_evt)
        work_q.put(run_evt)

        _proc_worker_wrapper_helper(
            mp, caplog, ScriptWorker, args=(work_q,), expect_shutdown_evt=True
        )
        env_args, _ = mock_env_fn.call_args
        assert env_args[0].msg_type == env_evt.msg_type
        mock_env_fn.assert_called_once()

        load_args, _ = mock_load_fn.call_args
        assert load_args[0].msg_type == load_evt.msg_type
        mock_load_fn.assert_called_once()

        run_args, _ = mock_run_fn.call_args
        assert run_args[0].msg_type == run_evt.msg_type
        mock_run_fn.assert_called_once()


class TestProcessManagerScriptWorkerIntegration:
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
        wait_for_state(manager, pid, ProcedureState.INITIALISING)
        expected = [
            ProcedureState.CREATING,  # ScriptWorker initialising
            ProcedureState.IDLE,  # ScriptWorker ready
            ProcedureState.LOADING,  # load user module
            ProcedureState.IDLE,  # user module loaded
            ProcedureState.INITIALISING,  # init present and called
        ]
        helper.assert_state_history(pid, expected)

        # let init complete, then check for completion
        resume.wait(0.1)
        resume.reset()  # reset to pause main method call
        wait_for_state(manager, pid, ProcedureState.READY)
        expected.append(ProcedureState.READY)  # init complete
        helper.assert_state_history(pid, expected)

        # now set main running
        manager.run(pid, call="main", run_args=ProcedureInput())
        expected.append(ProcedureState.RUNNING)  # main running
        main_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.RUNNING)
        helper.assert_state_history(pid, expected)

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
        helper.assert_state_history(pid, expected)

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
            # fail script has no init so no INITIALISING expected
            ProcedureState.READY,  # init complete
            ProcedureState.RUNNING,  # main running
            ProcedureState.FAILED,  # exception raised
        ]
        helper.wait_for_lifecycle(ProcedureState.FAILED)
        # wait_for_state(manager, pid, ProcedureState.FAILED)
        # helper.wait_for_message_on_topic(topics.procedure.lifecycle.stacktrace)
        helper.assert_state_history(pid, expected)

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

        wait_for_state(manager, pid, ProcedureState.READY)
        assert env.created.is_set()

    @patch("ska_oso_oet.procedure.domain.GitManager.clone_repo")
    @patch("ska_oso_oet.procedure.domain.subprocess.check_output")
    def test_shared_environment_waits_for_creation_to_complete(
        self, mock_subprocess_fn, mock_clone_fn, git_script, git_script_branch, manager
    ):
        """
        Verify calls to subprocess to install environment are only run if the environment does not yet exist.
        The first two scripts run in the same environment and the third one creates a new environment.
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
        mock_clone_fn.return_value = "/"
        calls = multiprocessing.Value("i", 0)

        def called(*args, **kwargs):
            calls.value += 1

        mock_subprocess_fn.side_effect = called

        pid1 = manager.create(git_script, init_args=ProcedureInput())
        env1 = manager.environments[pid1]
        pid2 = manager.create(git_script, init_args=ProcedureInput())
        env2 = manager.environments[pid2]

        assert env1 == env2

        wait_for_state(manager, pid1, ProcedureState.READY)
        wait_for_state(manager, pid2, ProcedureState.READY)

        # Subprocess should only be called twice because second script should
        # just wait for first one to create the environment
        assert calls.value == 2

        pid3 = manager.create(git_script_branch, init_args=ProcedureInput())
        env3 = manager.environments[pid3]

        wait_for_state(manager, pid3, ProcedureState.READY)

        assert env1 != env3
        assert env3.created.is_set()

        # Call count should go up because the new script should run in a new environment
        assert calls.value == 4

    @patch("ska_oso_oet.procedure.domain.GitManager.clone_repo")
    @patch("ska_oso_oet.procedure.domain.subprocess.check_output")
    def test_shared_environment_sys_path_is_set(
        self, mock_subprocess_fn, mock_clone_fn, git_sys_path_script, manager
    ):
        """
        Verify site packages are added to sys.path correctly for scripts sharing an environment.
        """
        site_pkg = "/python/site_packages"
        env = Environment(
            "123",
            multiprocessing.Event(),
            multiprocessing.Event(),
            "/",
            site_pkg,
        )
        manager.em.create_env = MagicMock()
        manager.em.create_env.side_effect = [env, env]

        # Return path to git file from clone call in env creation and module load
        mock_clone_fn.return_value = "/"

        pid1 = manager.create(git_sys_path_script, init_args=ProcedureInput(site_pkg))
        pid2 = manager.create(git_sys_path_script, init_args=ProcedureInput(site_pkg))
        wait_for_state(manager, pid1, ProcedureState.READY)
        wait_for_state(manager, pid2, ProcedureState.READY)

        # Running the main function asserts the site_pkg is in sys.path
        # If assertion fails, script state goes to FAILED, else it goes
        # to COMPLETE
        helper = PubSubHelper()
        manager.run(pid1, call="main", run_args=ProcedureInput(site_pkg))
        assert helper.wait_for_lifecycle(ProcedureState.COMPLETE, msg_src=pid1)

        manager.run(pid2, call="main", run_args=ProcedureInput(site_pkg))
        assert helper.wait_for_lifecycle(ProcedureState.COMPLETE, msg_src=pid2)

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
            ProcedureState.INITIALISING,  # init running
            ProcedureState.STOPPED,  # init stopped
        ]
        helper.wait_for_lifecycle(ProcedureState.STOPPED)
        helper.assert_state_history(pid, expected)

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
            ProcedureState.INITIALISING,  # init running
            ProcedureState.READY,  # init complete
            ProcedureState.RUNNING,  # main running
            ProcedureState.STOPPED,  # main stopped
        ]
        helper.assert_state_history(pid, expected)

    def test_running_not_set_on_init(self, manager, init_hang_script):
        """
        Verify that ProcessManager sets running procedure attribute to None
        when script is stopped
        """
        init_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(init_running)

        pid = manager.create(init_hang_script, init_args=init_args)
        init_running.wait(0.1)
        wait_for_state(manager, pid, ProcedureState.INITIALISING)
        assert manager.running is None

    def test_running_set_to_none_on_stop(self, manager, main_hang_script):
        """
        Verify that ProcessManager sets running procedure attribute to None
        when script is stopped
        """
        assert manager.running is None
        main_running = multiprocessing.Barrier(2)
        init_args = ProcedureInput(main_running)

        pid = manager.create(main_hang_script, init_args=init_args)
        wait_for_state(manager, pid, ProcedureState.READY)
        manager.run(pid, call="main", run_args=ProcedureInput())
        main_running.wait(0.5)
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

    def test_events_emitted_from_scripts_are_republished(self, manager, pubsub_script):
        """
        Verify that OET events are published at the appropriate times for a
        sad-path script.
        """
        helper = PubSubHelper()

        pid = manager.create(pubsub_script, init_args=ProcedureInput())
        wait_for_state(manager, pid, ProcedureState.READY)

        manager.run(pid, call="main", run_args=ProcedureInput(msg="foo"))
        helper.wait_for_message_on_topic(user_topics.script.announce)
        user_msgs = helper.messages_on_topic(user_topics.script.announce)
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
        ScriptWorker when script type is GitScript and create_env is True.
        """
        manager.ctx.Proc = MagicMock()
        manager.em.create_env = MagicMock()
        expected_env = Environment("1", None, None, "/", "/site-packages")
        manager.em.create_env.side_effect = [expected_env]
        git_script = GitScript(
            script_uri="git://test-script.py", git_args=GitArgs(), create_env=True
        )
        manager.create(git_script, init_args=ProcedureInput())
        q = manager.script_queues[1]
        env_msg = q.safe_get()
        assert env_msg.msg_type == "ENV"
        assert env_msg.msg == git_script

        _, kwargs = manager.ctx.Proc.call_args
        assert expected_env == kwargs["environment"]

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
        wait_for_state(manager, pid, ProcedureState.INITIALISING)
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

    def test_run_with_force_start(self, manager, script):
        """
        Verify that the run command is queued for a script even if the loading
        is not yet complete when force_start flag is set.
        """
        q = manager.ctx.MPQueue()
        manager.procedures[1] = MagicMock()
        manager.states[1] = ProcedureState.LOADING
        manager.script_queues[1] = q

        manager.run(1, call="main", run_args=ProcedureInput(), force_start=True)
        msg = q.safe_get(timeout=0.1)
        assert msg.msg_type == "RUN"

    def test_run_with_force_start_fails(self, manager, script):
        """
        Verify that the run command is not queued for a script even if forced
        if script is in a final state (STOPPED, COMPLETE, FAILED, UNKNOWN)
        """
        q = manager.ctx.MPQueue()
        manager.procedures[1] = MagicMock()
        manager.states[1] = ProcedureState.COMPLETE
        manager.script_queues[1] = q

        with pytest.raises(ValueError):
            manager.run(1, call="main", run_args=ProcedureInput(), force_start=True)

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

    def test_can_start_ready_procedure_while_another_procedure_is_initialising(
        self, manager: ProcessManager, barrier_script, init_hang_script
    ):
        """
        Confirm that it is possible to start a script while another script is
        initialising.

        In Sprint 17.5 Viivi found that it was not possible to begin execution
        of the main function while another script was initialising. We want
        this to be possible. This unit test should pass once the Procedure
        lifecycle has been refined and we have a clearer concept of
        initialising functions and 'main' functions. For now, this test
        illustrates the problem, raising an exception with 'ValueError:
        Cannot start PID 1: PID #2 is ProcedureState.RUNNING'.

        Test strategy is to:

        1. Create Procedure #1 that has a quick init
        2. Create Procedure #2 that hangs in init.
        3. Start Procedure #1
        4. confirm that Procedure #1 ran while Procedure #2 is still initialising
        """
        helper = PubSubHelper()

        # create and start Procedure #1, waiting for it to be ready
        p1_init_running = multiprocessing.Barrier(2)
        p1_main_running = multiprocessing.Barrier(2)
        p1_resume = multiprocessing.Barrier(2)
        p1_init_args = ProcedureInput(p1_init_running, p1_main_running, p1_resume)
        p1_pid = manager.create(barrier_script, init_args=p1_init_args)

        # start P1 init and let initialisation complete
        p1_init_running.wait(0.1)
        wait_for_state(manager, p1_pid, ProcedureState.INITIALISING)
        p1_resume.wait(0.1)
        p1_resume.reset()  # reset to pause main method call
        wait_for_state(manager, p1_pid, ProcedureState.READY)

        # create and start Procedure #2, the script that hangs in init
        p2_init_running = multiprocessing.Barrier(2)
        p2_init_args = ProcedureInput(p2_init_running)
        p2_pid = manager.create(init_hang_script, init_args=p2_init_args)
        p2_init_running.wait(0.1)
        wait_for_state(manager, p2_pid, ProcedureState.INITIALISING)

        # confirm test state is as expected: P1 ready, P2 initialising
        helper.assert_state(p1_pid, ProcedureState.READY)
        helper.assert_state(p2_pid, ProcedureState.INITIALISING)

        # now set P1 main running and wait for it to complete
        manager.run(p1_pid, call="main", run_args=ProcedureInput())
        p1_main_running.wait(0.1)
        p1_resume.wait(0.1)
        p1_resume.reset()  # reset to pause main method call
        wait_for_state(manager, p1_pid, ProcedureState.COMPLETE)

        # end test state should be that P1 ran successfully, P2 still initialising
        helper.assert_state(p1_pid, ProcedureState.COMPLETE)
        helper.assert_state(p2_pid, ProcedureState.INITIALISING)


class TestModuleFactory:
    @patch.object(ModuleFactory, "_load_module_from_git")
    def test_get_module_calls_git_load_function(self, mock_git_load):
        mock_git_load.side_effect = [MagicMock(importlib.machinery.SourceFileLoader)]

        git_script = GitScript(script_uri="git://test/script.py", git_args=GitArgs())
        _ = ModuleFactory.get_module(git_script)
        mock_git_load.assert_called_once_with(git_script)

    @patch.object(ModuleFactory, "_load_module_from_file")
    def test_get_module_calls_file_load_function(self, mock_file_load):
        mock_file_load.side_effect = [MagicMock(importlib.machinery.SourceFileLoader)]

        file_script = FileSystemScript(script_uri="file://test/script.py")
        _ = ModuleFactory.get_module(file_script)
        mock_file_load.assert_called_once_with(file_script.script_uri)

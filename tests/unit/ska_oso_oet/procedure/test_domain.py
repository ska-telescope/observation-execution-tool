# pylint: disable=W0613
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the ska_oso_oet.procedure.domain module.
"""
import multiprocessing
from multiprocessing import Manager
from queue import Empty
from unittest.mock import MagicMock

import pytest

from ska_oso_oet.procedure.domain import (
    PROCEDURE_QUEUE_MAX_LENGTH,
    FileSystemScript,
    GitArgs,
    GitScript,
    Procedure,
    ProcedureHistory,
    ProcedureInput,
    ProcedureState,
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
def fail_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("fail.py")
    script_path.write(
        """
def main(*args, **kwargs):
    raise Exception('oops!')
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

def main(l, item):
    time.sleep(2)
    l.add(item)
"""
    )
    return FileSystemScript(f"file://{str(script_path)}")


@pytest.fixture
def script_with_queue_path(tmpdir):
    """
    Pytest fixture to return a path to a script with main() which takes
    a queue and procedure as arguments and adds procedure process ID to queue.
    """
    path = tmpdir.join("script_with_queue.py")

    path.write(
        """
def main(queue, procedure):
    queue.put(procedure.pid)
"""
    )
    return FileSystemScript(f"file://{str(path)}")


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

def main(queue):
    queue.put(SCAN_ID_GENERATOR.next())
"""
    )
    return FileSystemScript(f"file://{str(path)}")


@pytest.fixture
def procedure(script):
    """
    Pytest fixture to return a prepared Procedure
    """
    return Procedure(script, 1, 2, 3, kw1="a", kw2="b")


@pytest.fixture
def manager():
    """
    Pytest fixture to return a prepared ProcessManager
    """
    return ProcessManager()


@pytest.fixture
def process_cleanup(manager):
    """
    Pytest fixture for waiting for Procedure process to finish before
    moving to next test. Should be used in tests where manager.run()
    is called but wait_for_process_to_complete() is not called
    """
    yield
    if multiprocessing.active_children():
        wait_for_process_to_complete(manager)


def wait_for_process_to_complete(manager, timeout=1):
    """
    Wait for script execution to complete and process to finish
    """
    with manager.procedure_complete:
        manager.procedure_complete.wait(timeout)


def test_git_args_input_accepts_expected_values():
    """
    Verify that GitArgs arguments.
    """
    git_args = GitArgs(
        git_repo="git://test.com", git_branch="master", git_commit="HEAD"
    )
    assert git_args.git_repo == "git://test.com"
    assert git_args.git_commit == "HEAD"


def test_git_args_input_eq_works_as_expected():
    """
    Verify GitArgs equality
    """
    ga1 = GitArgs("git://test.com", "HEAD", "master")
    ga2 = GitArgs("git://test.com", "HEAD", "master")
    ga3 = GitArgs("test")
    assert ga1 == ga2
    assert ga1 != ga3
    assert ga1 != object()


def test_git_args_default_values_are_as_expected():
    """
    Verify that GitArgs default values are set as
    expected if not provided.
    """
    git_args = GitArgs()
    assert git_args.git_repo == "git://gitlab.com/ska-telescope/ska-oso-scripting.git"
    assert git_args.git_branch == "master"
    assert git_args.git_commit is None


def test_procedure_input_accepts_expected_constructor_values():
    """
    Verify that ProcedureInput arguments are slurped into positional and
    keyword/value attributes.
    """
    procedure_input = ProcedureInput(1, 2, 3, a=1, b=2)
    assert procedure_input.args == (1, 2, 3)
    assert procedure_input.kwargs == dict(a=1, b=2)


def test_procedure_input_eq_works_as_expected():
    """
    Verify ProcedureInput equality
    """
    pi1 = ProcedureInput(1, 2, 3, a=1, b=2)
    pi2 = ProcedureInput(1, 2, 3, a=1, b=2)
    pi3 = ProcedureInput(4, a=1)
    assert pi1 == pi2
    assert pi1 != pi3
    assert pi1 != object()


def test_procedure_history_default_values_are_as_expected():
    """
    Verify that ProcedureHistory default values are set as
    expected if not provided.
    """
    procedure_history = ProcedureHistory()
    assert procedure_history.process_states == {}
    assert procedure_history.stacktrace is None


def test_procedure_history_eq_works_as_expected():
    """
    Verify ProcedureHistory equality
    """
    ph1 = ProcedureHistory()
    ph2 = ProcedureHistory()
    ph3 = ProcedureHistory([(ProcedureState.CREATED, 1601053634.9669704)])
    assert ph1 == ph2
    assert ph1 != ph3
    assert ph1 != object()


def test_id_of_a_new_procedure_is_none(procedure):
    """
    Verify that the ID of a new procedure is unset
    """
    assert procedure.id is None


def test_state_of_a_new_procedure_is_created(procedure):
    """
    Verify that the state of a new procedure is CREATED
    """
    assert procedure.state == ProcedureState.CREATED


def test_creation_of_a_new_procedure_is_added_to_history(procedure):
    """
    Verify that the CREATED state and time are recorded in procedure's history
    """
    assert ProcedureState.CREATED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.CREATED], float)


def test_procedure_start_sets_state_to_running(procedure):
    """
    Verify that procedure state changes to RUNNING when run() is called
    """
    procedure.start()
    assert procedure.state == ProcedureState.RUNNING


def test_procedure_run_executes_user_script(script_with_queue_path):
    """
    Verify that user script executes when run() is called
    """
    procedure = Procedure(script=script_with_queue_path)
    queue = multiprocessing.Queue()
    procedure.script_args["run"].args = [queue, procedure]
    procedure.run()
    assert queue.get(timeout=1) is None
    with pytest.raises(Empty):
        queue.get(block=False)


def test_procedure_run_catches_and_stores_script_exception(fail_script):
    """
    Verify that run() catches an exception thrown in a script and places
    it in the stacktrace queue
    """
    procedure = Procedure(script=fail_script)
    procedure.run()
    try:
        procedure.stacktrace_queue.get(timeout=1)
    except Exception:  # pylint: disable=broad-except
        # test should not raise an exception, so fail if it does
        pytest.fail("Stacktrace not found in queue")


def test_procedure_start_executes_user_script_in_child_process(script_with_queue_path):
    """
    Verify that user script executes in a separate (child) process when run() is called
    """
    procedure = Procedure(script=script_with_queue_path)
    queue = multiprocessing.Queue()
    procedure.script_args["run"].args = [queue, procedure]
    procedure.start()
    procedure.join()
    assert not queue.empty()
    assert queue.get() is not None


def test_runtime_arguments_are_passed_to_user_script(procedure):
    """
    Verify that arguments passed from procedure are accessible in the user script
    """
    run_args = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
    procedure.script_args["run"] = run_args
    procedure.user_module = MagicMock()
    procedure.run()
    procedure.user_module.main.assert_called_with(5, 6, 7, kw3="c", kw4="d")


def test_procedure_start_raises_exception_on_a_running_procedure(procedure):
    """
    Verify that a RUNNING procedure can not be run again
    """
    procedure.start()
    with pytest.raises(Exception):
        procedure.start()


def test_procedure_init_stores_initial_arguments(procedure):
    """
    Verify that the procedure constructor arguments are captured and persisted
    on the procedure instance.
    """
    assert procedure.script_args["init"] == ProcedureInput(1, 2, 3, kw1="a", kw2="b")


def test_procedure_init_raises_exception_on_script_file_not_found():
    """
    Verify that FileNotFoundError is raised if script file does not exist
    """
    script = FileSystemScript("file://abcbs")

    with pytest.raises(FileNotFoundError):
        _ = Procedure(script=script)


def test_procedure_terminate_sets_state_to_stopped(procedure):
    """
    Verify that procedure terminate changes to STOPPED
    when terminate() is called
    """
    procedure.start()
    procedure.terminate()
    assert procedure.state == ProcedureState.STOPPED


def test_procedure_terminate_records_state_in_history(procedure):
    """
    Verify that procedure terminate records STOPPED state in the history
    """
    procedure.start()
    procedure.terminate()
    assert ProcedureState.CREATED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.CREATED], float)
    assert ProcedureState.STOPPED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.STOPPED], float)


def test_procedure_terminate_not_allowed_if_process_is_not_running(procedure):
    """
    Verify that procedure raises an exception if process to terminate
    is not in RUNNING state
    """
    with pytest.raises(Exception):
        procedure.terminate()


def test_no_procedures_running_on_a_new_process_manager(manager):
    """
    Verify that a new ProcessManager has no running procedure
    """
    assert manager.running is None


def test_no_procedures_stores_on_a_new_process_manager(manager):
    """
    Verify that a new ProcessManager has no procedures
    """
    assert not manager.procedures


def test_process_manager_create_sets_pid_of_new_procedure(manager, script):
    """
    Verify that procedures are assigned IDs on process creation
    """
    pid = manager.create(script, init_args=ProcedureInput())
    created = manager.procedures[pid]
    assert created.id == pid


def test_process_manager_create_adds_new_procedure(manager, script):
    """
    Verify that ProcessManager keeps references to the processes it creates
    """
    len_before = len(manager.procedures)
    manager.create(script, init_args=ProcedureInput())
    assert len(manager.procedures) == len_before + 1


def test_process_manager_create_removes_oldest_procedure_on_max_procedures(
    manager, script
):
    """
    Verify that ProcessManager removes the oldest procedure when the maximum number of
    saved procedures is reached
    """
    manager.procedures.clear()
    max_procedures = PROCEDURE_QUEUE_MAX_LENGTH
    for _ in range(len(manager.procedures), max_procedures):
        manager.create(script, init_args=ProcedureInput())

    assert len(manager.procedures) == max_procedures
    assert 1 in manager.procedures

    # adding procedure should not increase the number of procedures
    # and should remove the oldest procedure (with ID 1)
    manager.create(script, init_args=ProcedureInput())

    assert len(manager.procedures) == max_procedures
    assert 1 not in manager.procedures


def test_process_manager_create_captures_initialisation_arguments(manager, script):
    """
    Verify that ProcessManager passes through initialisation arguments to
    the procedures it creates
    """
    expected = ProcedureInput(1, 2, 3, a=4, b=5)
    pid = manager.create(script, init_args=expected)
    created = manager.procedures[pid]
    assert created.script_args["init"] == expected


def test_process_manager_create_captures_git_arguments(manager, script):
    """
    Verify that ProcessManager passes through git arguments to the procedures it creates
    """
    expected = GitArgs(git_repo="http://foo.git", git_commit="HEAD", git_branch="main")
    git_script = GitScript(script_uri=script.script_uri, git_args=expected)
    pid = manager.create(git_script, init_args=ProcedureInput())
    created = manager.procedures[pid]
    assert isinstance(created.script, GitScript)
    assert created.script.git_args == expected


def test_calling_process_manager_run_sets_run_args_on_procedure(
    manager, script, process_cleanup
):
    """
    Verify that the arguments to ProcessManager run() are captured and stored on the
    procedure instance
    """
    pid = manager.create(script, init_args=ProcedureInput())
    expected = ProcedureInput(5, 6, 7, kw3="c", kw4="d")
    created = manager.procedures[pid]
    manager.run(pid, run_args=expected)
    assert created.script_args["run"] == expected


def test_process_manager_run_changes_state_of_procedure_to_running(
    manager, script, process_cleanup
):
    """
    Verify that procedure state changes when ProcessManager starts
    procedure execution
    """
    pid = manager.create(script, init_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.CREATED
    manager.run(pid, run_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.RUNNING


def test_process_manager_run_executes_procedure_start(manager, process_cleanup):
    """
    Verify that a call to ProcessManager run() executes Procedure.start()
    instead of Procedure.run(). This confirms that Procedure will execute in a
    child process.
    """
    procedure = MagicMock()
    manager.procedures[1] = procedure
    manager.run(1, run_args=ProcedureInput())
    procedure.start.assert_called_once()


def test_process_manager_run_sets_running_procedure(manager, tmpdir, process_cleanup):
    """
    Verify that ProcessManager sets the running procedure attribute
    appropriately when run() is called
    """
    script_path = tmpdir.join("sleep.py")
    script_path.write(
        """
def main(shutdown_event, *args, **kwargs):
    while not shutdown_event.is_set():
        continue
"""
    )
    script = FileSystemScript(f"file://{str(script_path)}")

    shutdown_event = multiprocessing.Event()
    pid = manager.create(script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput(shutdown_event))
    assert manager.running == manager.procedures[pid]
    shutdown_event.set()


def test_process_manager_sets_running_to_none_when_process_completes(manager, script):
    """
    Verify that ProcessManager sets running procedure attribute to None
    when process completes
    """
    pid = manager.create(script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    assert manager.running is None


def test_process_manager_updates_state_of_completed_procedures(manager, script):
    """
    Verify that ProcessManager updates procedure state to COMPLETED when finished
    successfully
    """
    pid = manager.create(script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    assert manager.procedures[pid].state == ProcedureState.COMPLETED


def test_process_manager_updates_history_of_completed_procedures(manager, script):
    """
    Verify that ProcessManager updates procedure state to COMPLETED when finished
    successfully
    """
    pid = manager.create(script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    procedure = manager.procedures[pid]

    assert ProcedureState.CREATED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.CREATED], float)
    assert ProcedureState.RUNNING in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.RUNNING], float)
    assert ProcedureState.COMPLETED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.COMPLETED], float)
    assert procedure.history.stacktrace is None


def test_process_manager_sets_running_to_none_on_script_failure(manager, fail_script):
    """
    Verify that ProcessManager sets running procedure attribute to None
    when script execution fails
    """
    pid = manager.create(fail_script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    assert manager.running is None


def test_process_manager_updates_procedure_state_on_script_failure(
    manager, fail_script
):
    """
    Verify that ProcessManager removes a failed procedure from
    the procedures list
    """
    pid = manager.create(fail_script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    assert manager.procedures[pid].state == ProcedureState.FAILED


def test_process_manager_updates_procedure_history_on_script_failure(
    manager, fail_script
):
    """
    Verify that ProcessManager updates FAILED to procedure history when script fails
    """
    pid = manager.create(fail_script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    wait_for_process_to_complete(manager)
    procedure = manager.procedures[pid]

    assert ProcedureState.CREATED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.CREATED], float)
    assert ProcedureState.RUNNING in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.RUNNING], float)
    assert ProcedureState.FAILED in procedure.history.process_states
    assert isinstance(procedure.history.process_states[ProcedureState.FAILED], float)
    assert procedure.history.stacktrace is not None


def test_process_manager_run_fails_on_invalid_pid(manager):
    """
    Verify that an exception is raised when run() is requested for an invalid
    PID
    """
    with pytest.raises(ValueError):
        manager.run(321, run_args=ProcedureInput())


def test_process_manager_run_fails_on_process_that_is_already_running(
    manager, script, process_cleanup
):
    """
    Verify that an exception is raised when requesting run() for a procedure
    that is already running
    """
    pid = manager.create(script, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    with pytest.raises(ValueError):
        manager.run(pid, run_args=ProcedureInput())


def test_process_manager_stop_terminates_the_process(manager, abort_script):
    """
    Verify that ProcessManager stops a script execution
    """
    with Manager() as mp_mgr:
        pid = manager.create(abort_script, init_args=ProcedureInput())
        lst = mp_mgr.list()
        manager.run(pid, run_args=ProcedureInput(lst, pid))
        manager.stop(pid)
        wait_for_process_to_complete(manager, timeout=3)
        assert len(lst) == 0


def test_process_manager_sets_running_to_none_on_stop(manager, abort_script):
    """
    Verify that ProcessManager sets running procedure attribute to None
    when script is stopped
    """
    with Manager() as mp_mgr:
        pid = manager.create(abort_script, init_args=ProcedureInput())
        lst = mp_mgr.list()
        manager.run(pid, run_args=ProcedureInput(lst, pid))
        manager.stop(pid)
        wait_for_process_to_complete(manager)
        assert manager.running is None


def test_process_manager_updates_procedure_state_on_stop(manager, abort_script):
    """
    Verify that ProcessManager removes an stopped procedure from
    the procedures list
    """
    with Manager() as mp_mgr:
        pid = manager.create(abort_script, init_args=ProcedureInput())
        lst = mp_mgr.list()
        manager.run(pid, run_args=ProcedureInput(lst, pid))
        manager.stop(pid)
        wait_for_process_to_complete(manager)
        assert manager.procedures[pid].state == ProcedureState.STOPPED


def test_process_manager_stop_fails_on_invalid_pid(manager):
    """
    Verify that an exception is raised when stop() is requested for an invalid
    PID
    """
    with pytest.raises(ValueError):
        manager.stop(321)


def test_process_manager_stop_fails_on_process_that_is_not_running(manager, script):
    """
    Verify that an exception is raised when requesting stop() for a procedure
    that is not running
    """
    pid = manager.create(script, init_args=ProcedureInput())
    with pytest.raises(ValueError):
        manager.stop(pid)


def test_scan_id_persists_between_executions(
    script_that_increments_and_returns_scan_id,
):
    """
    The scan ID should be shared and persisted between process executions.
    """
    manager = ProcessManager()
    queue = multiprocessing.Queue()
    run_args = ProcedureInput(queue)

    pid = manager.create(
        script=script_that_increments_and_returns_scan_id,
        init_args=ProcedureInput(),
    )
    manager.run(pid, run_args=run_args)
    wait_for_process_to_complete(manager)
    scan_id = queue.get(timeout=1)

    pid = manager.create(
        script=script_that_increments_and_returns_scan_id,
        init_args=ProcedureInput(),
    )
    manager.run(pid, run_args=run_args)
    wait_for_process_to_complete(manager)
    next_scan_id = queue.get(timeout=1)

    assert next_scan_id == scan_id + 1

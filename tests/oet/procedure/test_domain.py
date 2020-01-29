"""
Unit tests for the oet.procedure.domain module.
"""
import pytest
import multiprocessing
from unittest.mock import MagicMock

from oet.procedure.domain import Procedure, ProcedureState, ProcedureInput, ProcessManager

@pytest.fixture
def script_path(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("script.py")
    script_path.write("def main(*args, **kwargs):\n\tpass")
    return script_path

@pytest.fixture
def script_with_queue_path(tmpdir):
    """
    Pytest fixture to return a path to a script with main() which takes
    a queue and procedure as arguments and adds procedure process ID to queue.
    """
    path = tmpdir.join("script_with_queue.py")

    path.write("""
def main(queue, procedure):
    queue.put(procedure.pid)
""")
    return path

@pytest.fixture
def procedure(script_path):
    """
    Pytest fixture to return a prepared Procedure
    """
    return Procedure(script_path, 1, 2, 3, kw1='a', kw2='b')


@pytest.fixture
def manager():
    """
    Pytest fixture to return a prepared ProcessManager
    """
    return ProcessManager()


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


def test_id_of_a_new_procedure_is_none(procedure):
    """
    Verify that the ID of a new procedure is unset
    """
    assert procedure.id is None


def test_state_of_a_new_procedure_is_ready(procedure):
    """
    Verify that the state of a new procedure is READY
    """
    assert procedure.state == ProcedureState.READY


def test_procedure_run_sets_state_to_running(procedure):
    """
    Verify that procedure state changes to RUNNING when run() is called
    """
    procedure.run()
    assert procedure.state == ProcedureState.RUNNING


def test_procedure_run_executes_user_script(tmpdir, script_with_queue_path):
    """
    Verify that user script executes when run() is called
    """
    procedure = Procedure(script_uri=script_with_queue_path)
    queue = multiprocessing.Queue()
    procedure.script_args['run'].args = [queue, procedure]
    procedure.run()
    assert queue.qsize() == 1
    assert queue.get() is None


def test_procedure_run_executes_user_script_in_child_process(tmpdir, script_with_queue_path):
    """
    Verify that user script executes in a separate (child) process when run() is called
    """
    procedure = Procedure(script_uri=script_with_queue_path)
    queue = multiprocessing.Queue()
    procedure.script_args['run'].args = [queue, procedure]
    procedure.start()
    procedure.join()
    assert not queue.empty()
    assert queue.get() is not None


def test_runtime_arguments_are_passed_to_user_script(procedure):
    """
    Verify that arguments passed from procedure are accessible in the user script
    """
    run_args = ProcedureInput(5, 6, 7, kw3='c', kw4='d')
    procedure.script_args['run'] = run_args
    procedure.user_module = MagicMock()
    procedure.run()
    procedure.user_module.main.assert_called_with(5, 6, 7, kw3='c', kw4='d')


def test_procedure_run_raises_exception_on_a_running_procedure(procedure):
    """
    Verify that a RUNNING procedure can not be run again
    """
    procedure.run()
    with pytest.raises(Exception):
        procedure.run()


def test_procedure_init_stores_initial_arguments(procedure):
    """
    Verify that the procedure constructor arguments are captured and persisted
    on the procedure instance.
    """
    assert procedure.script_args['init'] == ProcedureInput(1, 2, 3, kw1='a', kw2='b')


def test_procedure_init_raises_exception_on_script_file_not_found():
    """
    Verify that FileNotFoundError is raised if script file does not exist
    """
    script_uri = 'file://abcbs'

    with pytest.raises(FileNotFoundError):
        _ = Procedure(script_uri=script_uri)


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


def test_process_manager_create_sets_pid_of_new_procedure(manager, script_path):
    """
    Verify that procedures are assigned IDs on process creation
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    created = manager.procedures[pid]
    assert created.id == pid


def test_process_manager_create_adds_new_procedure(manager, script_path):
    """
    Verify that ProcessManager keeps references to the processes it creates
    """
    len_before = len(manager.procedures)
    manager.create(script_path, init_args=ProcedureInput())
    assert len(manager.procedures) == len_before + 1


def test_process_manager_create_captures_initialisation_arguments(manager, script_path):
    """
    Verify that ProcessManager passes through initialisation arguments to
    the procedures it creates
    """
    expected = ProcedureInput(1, 2, 3, a=4, b=5)
    pid = manager.create(script_path, init_args=expected)
    created = manager.procedures[pid]
    assert created.script_args['init'] == expected


def test_calling_process_manager_run_sets_run_args_on_procedure(manager, script_path):
    """
    Verify that the arguments to ProcessManager run() are captured and stored on the
    procedure instance
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    expected = ProcedureInput(5, 6, 7, kw3='c', kw4='d')
    created = manager.procedures[pid]
    manager.run(pid, run_args=expected)
    assert created.script_args['run'] == expected

# TODO: Fix this (should Procedure state be changed in ProcessManager and not in Procedure run()?)
def test_process_manager_run_changes_state_of_procedure_to_running(manager, script_path):
    """
    Verify that procedure state changes when ProcessManager starts
    procedure execution
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.READY
    manager.run(pid, run_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.RUNNING


def test_process_manager_run_executes_user_script_in_child_process(manager, script_path):
    """
    Verify that a call to ProcessManager run() does not wait for procedure to finish
    script execution before returning.
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    procedure = manager.procedures[pid]
    run_args = ProcedureInput()
    manager.run(pid, run_args=run_args)
    assert procedure.is_alive()


def test_process_manager_run_sets_running_procedure(manager, script_path):
    """
    Verify that ProcessManager sets the running procedure attribute
    appropriately when run() is called
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    assert manager.running == manager.procedures[pid]


def test_process_manager_sets_running_to_none_when_process_completes(manager):
    """
    Verify that ProcessManager sets running procedure attribute to None
    when process completes
    """
    pytest.fail()


def test_process_manager_removes_references_to_completed_procedures(manager):
    """
    Verify that ProcessManager removes a completed procedure from
    the procedures list
    """
    pytest.fail()


def test_process_manager_sets_running_to_none_on_script_failure(manager):
    """
    Verify that ProcessManager sets running procedure attribute to None
    when script execution fails
    """
    pytest.fail()


def test_process_manager_removes_references_on_script_failure(manager):
    """
    Verify that ProcessManager removes a failed procedure from
    the procedures list
    """
    pytest.fail()


def test_process_manager_run_fails_on_invalid_pid(manager):
    """
    Verify that an exception is raised when run() is requested for an invalid
    PID
    """
    with pytest.raises(ValueError):
        manager.run(321, run_args=ProcedureInput())


def test_process_manager_run_fails_on_process_that_is_already_running(manager, script_path):
    """
    Verify that an exception is raised when requesting run() for a procedure
    that is already running
    """
    pid = manager.create(script_path, init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    with pytest.raises(ValueError):
        manager.run(pid, run_args=ProcedureInput())

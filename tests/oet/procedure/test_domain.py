"""
Unit tests for the oet.procedure.domain module.
"""
import pytest

from oet.procedure.domain import Procedure, ProcedureState, ProcedureInput, ProcessManager


@pytest.fixture
def procedure():
    """
    Pytest fixture to return a prepared Procedure
    """
    return Procedure('file://path/to/my/script.py', 1, 2, 3, kw1='a', kw2='b')


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


def test_procedure_run_stores_arguments(procedure):
    """
    Verify that the arguments to run() are captured and stored on the
    procedure instance
    """
    procedure.run(5, 6, 7, kw3='c', kw4='d')
    assert procedure.script_args['run'] == ProcedureInput(5, 6, 7, kw3='c', kw4='d')


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


def test_process_manager_create_sets_pid_of_new_procedure(manager):
    """
    Verify that procedures are assigned IDs on process creation
    """
    pid = manager.create('file:///test.py', init_args=ProcedureInput())
    created = manager.procedures[pid]
    assert created.id == pid


def test_process_manager_create_adds_new_procedure(manager):
    """
    Verify that ProcessManager keeps references to the processes it creates
    """
    len_before = len(manager.procedures)
    manager.create('file:///test.py', init_args=ProcedureInput())
    assert len(manager.procedures) == len_before + 1


def test_process_manager_create_captures_initialisation_arguments(manager):
    """
    Verify that ProcessManager passes through initialisation arguments to
    the procedures it creates
    """
    expected = ProcedureInput(1, 2, 3, a=4, b=5)
    pid = manager.create('file:///test.py', init_args=expected)
    created = manager.procedures[pid]
    assert created.script_args['init'] == expected


def test_process_manager_run_changes_state_of_procedure_to_running(manager):
    """
    Verify that procedure state changes when ProcessManager starts
    procedure execution
    """
    pid = manager.create('file:///test.py', init_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.READY
    manager.run(pid, run_args=ProcedureInput())
    assert manager.procedures[pid].state == ProcedureState.RUNNING


def test_process_manager_run_sets_running_procedure(manager):
    """
    Verify that ProcessManager sets the running procedure attribute
    appropriately when run() is called
    """
    pid = manager.create('file:///test.py', init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    assert manager.running == manager.procedures[pid]


def test_process_manager_run_fails_on_invalid_pid(manager):
    """
    Verify that an exception is raised when run() is requested for an invalid
    PID
    """
    with pytest.raises(ValueError):
        manager.run(321, run_args=ProcedureInput())


def test_process_manager_run_fails_on_process_that_is_already_running(manager):
    """
    Verify that an exception is raised when requesting run() for a procedure
    that is already running
    """
    pid = manager.create('file:///test.py', init_args=ProcedureInput())
    manager.run(pid, run_args=ProcedureInput())
    with pytest.raises(ValueError):
        manager.run(pid, run_args=ProcedureInput())

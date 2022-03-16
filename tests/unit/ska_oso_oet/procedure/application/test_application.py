# pylint: disable=W0212
# - W0212(protected-access) - tests need to access protected props
"""
Unit tests for the ska_oso_oet.procedure.application module.
"""

import unittest.mock as mock

import pytest

from ska_oso_oet.procedure.application.application import (
    PrepareProcessCommand,
    ScriptExecutionService,
    StartProcessCommand,
    StopProcessCommand,
)
from ska_oso_oet.procedure.domain import (
    Procedure,
    ProcedureHistory,
    ProcedureInput,
    ProcedureState,
    ProcedureSummary,
)


@pytest.fixture
def abort_script(tmpdir):
    """
    Pytest fixture to return a path to a script file
    """
    script_path = tmpdir.join("abort.py")
    script_path.write(
        """
import time

def main(queue, procedure):
    time.sleep(2)
    queue.put(procedure.pid)
"""
    )
    return f"file://{str(script_path)}"


def create_empty_procedure_summary(
    procedure_id: int, script_uri: str, history: ProcedureHistory
):
    """
    Utility function to create a null procedure summary. The returned
    procedure defines zero script arguments.

    :param procedure_id: procedure ID
    :param script_uri: path to script
    :param history: Procedure history
    :return: corresponding ProcedureSummary object
    """
    return ProcedureSummary(
        id=procedure_id,
        script_uri=script_uri,
        script_args={"init": ProcedureInput(), "run": ProcedureInput()},
        history=history,
        state=ProcedureState.CREATED,
    )


def test_ses_create_summary_returns_empty_list_when_no_procedures_present():
    """
    Verify that ScriptExecutionService.summarise() works when no procedures
    have been requested.
    """
    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        instance = mock_pm.return_value
        instance.procedures = {}
        service = ScriptExecutionService()
        procedures = service.summarise()
        assert procedures == []


def test_ses_create_summary_returns_expected_object():
    """
    Verify that the private method _create_summary converts from Procedures to
    ProcedureSummary correctly
    """
    procedure = Procedure("test://test.py", 1, 2, 3, procedure_id=123, kw1=4, kw2=5)
    procedures = {123: procedure}
    expected = ProcedureSummary(
        id=123,
        script_uri=procedure.script_uri,
        script_args=procedure.script_args,
        history=procedure.history,
        state=procedure.state,
    )
    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        instance = mock_pm.return_value
        instance.procedures = procedures
        service = ScriptExecutionService()
        summary = service._create_summary(123)  # pylint: disable=protected-access
        assert summary == expected


def test_ses_prepare_call_sequence_and_returns_summary_for_created_process():
    """
    Verify that ScriptExecutionService.prepare() calls the appropriate domain
    object methods for process creation and returns the expected summary object
    """
    script_uri = "test://test.py"
    cmd = PrepareProcessCommand(script_uri=script_uri, init_args=ProcedureInput())
    procedure = Procedure(script_uri, procedure_id=123)
    procedures = {123: procedure}
    expected = ProcedureSummary(
        id=123,
        script_uri=procedure.script_uri,
        script_args=procedure.script_args,
        history=procedure.history,
        state=procedure.state,
    )

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # tell ProcessManager.create to return PID 123, which is subsequently
        # used for lookup
        instance.create.return_value = 123
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service.prepare(cmd)

        instance.create.assert_called_once_with(script_uri, init_args=ProcedureInput())
        assert returned == expected


def test_ses_start_calls_process_manager_function_and_returns_summary():
    """
    Verify that ScriptExecutionService.start() calls the appropriate domain
    object methods for starting process execution and returns the expected
    summary object
    """
    script_uri = "test://test.py"
    cmd = StartProcessCommand(process_uid=123, run_args=ProcedureInput())
    procedure = Procedure(script_uri, procedure_id=123)
    procedures = {123: procedure}
    expected = ProcedureSummary(
        id=123,
        script_uri=procedure.script_uri,
        script_args=procedure.script_args,
        history=procedure.history,
        state=procedure.state,
    )

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service.start(cmd)

        # service should call run() and return the summary for the executed
        # procedure
        instance.run.assert_called_once_with(123, run_args=ProcedureInput())
        assert returned == expected
        # we don't validate or modify procedure state, so this should still be
        # READY rather than RUNNING
        assert returned.state == ProcedureState.CREATED


def test_ses_summarise_returns_summaries_for_requested_pids():
    """
    ScriptExecutionService.summarise() should only return status for requested
    procedures.
    """
    procedure_a = Procedure("test://a", procedure_id=1)
    procedure_b = Procedure("test://b", procedure_id=2)
    procedure_c = Procedure("test://c", procedure_id=3)
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    expected = [
        create_empty_procedure_summary(1, "test://a", procedure_a.history),
        create_empty_procedure_summary(3, "test://c", procedure_c.history),
    ]

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service.summarise([1, 3])

        assert returned == expected


def test_ses_summarise_fails_when_invalid_pid_requested():
    """
    Verify that ScriptExecutionService.summarise() fails when an invalid
    procedure ID is requested.
    """
    procedure_a = Procedure("test://a")
    procedure_b = Procedure("test://b")
    procedure_c = Procedure("test://c")
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        with pytest.raises(ValueError):
            service.summarise([543534])


def test_ses_summarise_returns_all_summaries_when_no_pid_requested():
    """
    Verify that summaries for all procedures are returned when no specific PID
    is requested.
    """
    procedure_a = Procedure("test://a", procedure_id=1)
    procedure_b = Procedure("test://b", procedure_id=2)
    procedure_c = Procedure("test://c", procedure_id=3)
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    expected = [
        create_empty_procedure_summary(1, "test://a", procedure_a.history),
        create_empty_procedure_summary(2, "test://b", procedure_b.history),
        create_empty_procedure_summary(3, "test://c", procedure_c.history),
    ]

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service.summarise()

        assert returned == expected


def test_ses_stop_calls_process_manager_function(abort_script):
    """
    Verify that ScriptExecutionService.stop() calls the appropriate
    ProcessManager methods to stop process execution, then prepares and
    starts a new Process running the abort script.
    """
    # Test script/procedures will target sub-array 2
    subarray_id = 4
    # PID of running script
    running_pid = 50
    # PID of new abort Process will be 123
    abort_pid = 123

    # Create Procedure representing the script to be stopped
    procedure_to_stop = Procedure(
        "test://a", procedure_id=running_pid, subarray_id=subarray_id
    )

    # Create second Procedure to represent the Process running the
    # post-termination abort script
    abort_procedure = Procedure(
        abort_script, procedure_id=abort_pid, subarray_id=subarray_id
    )

    # Prepare a dict of PIDs to Procedures that we can use to mock the internal
    # data structure held by ProcessManager. This dict is read by the SES when
    # when summarising the prepared and running processes.
    process_manager_procedures = {running_pid: procedure_to_stop}

    # When SES.stop() is called, the SES should stop the current process,
    # prepare a process for the abort script, then set the abort process
    # running..
    cmd_stop = StopProcessCommand(process_uid=running_pid, run_abort=True)
    cmd_create = PrepareProcessCommand(
        script_uri=abort_script, init_args=abort_procedure.script_args["init"]
    )
    cmd_run = StartProcessCommand(
        process_uid=abort_pid, run_args=abort_procedure.script_args["run"]
    )

    # .. before returning a summary of the running abort Process
    expected = [
        ProcedureSummary(
            id=abort_pid,
            script_uri=abort_procedure.script_uri,
            script_args=abort_procedure.script_args,
            history=abort_procedure.history,
            state=abort_procedure.state,
        )
    ]

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance, preparing it for SES access
        instance = mock_pm.return_value
        instance.procedures = process_manager_procedures

        def create_abort(*_, **__):
            # The real .create() function would add the abort procedure to its
            # internal data structure when called
            process_manager_procedures[abort_pid] = abort_procedure
            return abort_pid

        instance.create.side_effect = create_abort

        service = ScriptExecutionService(abort_script_uri=abort_script)
        returned = service.stop(cmd_stop)

        # service should call stop -> create -> run, then return list containing
        # summary
        instance.stop.assert_called_once_with(cmd_stop.process_uid)
        instance.create.assert_called_once_with(
            cmd_create.script_uri, init_args=cmd_create.init_args
        )
        instance.run.assert_called_once_with(
            cmd_run.process_uid, run_args=cmd_run.run_args
        )
        assert returned == expected


def test_ses_stop_calls_process_manager_function_with_no_script_execution(abort_script):
    """
    Verify that ScriptExecutionService.stop() calls the appropriate domain
    object methods for stopping process execution without executing abort
    python script.
    """
    # PID of running process
    running_pid = 123

    # Test script/procedures will target sub-array 2
    init_args = ProcedureInput(subarray_id=2)

    # Create Procedure representing the script to be stopped
    procedure_to_stop = Procedure("test://a")
    procedure_to_stop.script_args["init"] = init_args

    # Prepare a dict of PIDs to Procedures that we can use to mock the internal
    # data structure held by ProcessManager.
    process_manager_procedures = {running_pid: procedure_to_stop}

    cmd = StopProcessCommand(process_uid=running_pid, run_abort=False)
    # returned summary list should be empty if abort script is bypassed
    expected = []

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance, preparing it for SES access
        instance = mock_pm.return_value
        instance.procedures = process_manager_procedures

        service = ScriptExecutionService(abort_script_uri=abort_script)
        returned = service.stop(cmd)

        # service should call stop() and return empty list
        instance.stop.assert_called_once_with(running_pid)
        assert returned == expected


def test_ses_get_subarray_id_for_requested_pid():
    """
    Verify that the private method _get_subarray_id returns
    subarray id correctly
    """
    subarray_id = 123
    process_pid = 456

    procedure = Procedure("test://a")
    init_args = ProcedureInput(subarray_id=subarray_id)
    procedure.script_args["init"] = init_args
    procedures = {process_pid: procedure}
    process_summary = ProcedureSummary(
        id=process_pid,
        script_uri=procedure.script_uri,
        script_args=procedure.script_args,
        history=procedure.history,
        state=procedure.state,
    )
    expected = [process_summary]

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service._get_subarray_id(process_pid)

        assert returned == expected[0].script_args["init"].kwargs["subarray_id"]


def test_ses_get_subarray_id_fails_on_missing_subarray_id():
    """
    Verify that an exception is raised when subarray id is missing for requested
    PID
    """
    procedure = Procedure("test://a")
    procedures = {1: procedure}

    with mock.patch(
        "ska_oso_oet.procedure.application.application.domain.ProcessManager"
    ) as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        with pytest.raises(ValueError):
            service._get_subarray_id(1)  # pylint: disable=protected-access

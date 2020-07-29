"""
Unit tests for the oet.procedure.application module.
"""

import unittest.mock as mock

import pytest

from oet.procedure.application.application import ScriptExecutionService, ProcedureSummary, \
    PrepareProcessCommand, StartProcessCommand, StopProcessCommand
from oet.procedure.domain import Procedure, ProcedureInput, ProcedureState


def create_empty_procedure_summary(procedure_id: int, script_uri: str):
    """
    Utility function to create a null procedure summary. The returned
    procedure defines zero script arguments.

    :param procedure_id: procedure ID
    :param script_uri: path to script
    :return: corresponding ProcedureSummary object
    """
    return ProcedureSummary(id=procedure_id,
                            script_uri=script_uri,
                            script_args={'init': ProcedureInput(), 'run': ProcedureInput()},
                            state=ProcedureState.READY)


def test_ses_create_summary_returns_empty_list_when_no_procedures_present():
    """
    Verify that ScriptExecutionService.summarise() works when no procedures
    have been requested.
    """
    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
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
    procedure = Procedure('test://test.py', 1, 2, 3, kw1=4, kw2=5)
    procedures = {123: procedure}
    expected = ProcedureSummary(id=123, script_uri=procedure.script_uri,
                                script_args=procedure.script_args,
                                state=procedure.state)
    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
        instance = mock_pm.return_value
        instance.procedures = procedures
        service = ScriptExecutionService()
        summary = service._create_summary(123)  # pylint: disable=protected-access
        assert summary == expected


def test_ses_prepare_calls_process_manager_method_and_returns_summary_for_created_process():
    """
    Verify that ScriptExecutionService.prepare() calls the appropriate domain
    object methods for process creation and returns the expected summary object
    """
    script_uri = 'test://test.py'
    cmd = PrepareProcessCommand(script_uri=script_uri, init_args=ProcedureInput())
    procedure = Procedure(script_uri)
    procedures = {123: procedure}
    expected = ProcedureSummary(id=123, script_uri=procedure.script_uri,
                                script_args=procedure.script_args,
                                state=procedure.state)

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
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
    script_uri = 'test://test.py'
    cmd = StartProcessCommand(process_uid=123, run_args=ProcedureInput())
    procedure = Procedure(script_uri)
    procedures = {123: procedure}
    expected = ProcedureSummary(id=123, script_uri=procedure.script_uri,
                                script_args=procedure.script_args,
                                state=procedure.state)

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
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
        assert returned.state == ProcedureState.READY


def test_ses_summarise_returns_summaries_for_requested_pids():
    """
    ScriptExecutionService.summarise() should only return status for requested
    procedures.
    """
    procedure_a = Procedure('test://a')
    procedure_b = Procedure('test://b')
    procedure_c = Procedure('test://c')
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    expected = [
        create_empty_procedure_summary(1, 'test://a'),
        create_empty_procedure_summary(3, 'test://c')
    ]

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
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
    procedure_a = Procedure('test://a')
    procedure_b = Procedure('test://b')
    procedure_c = Procedure('test://c')
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
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
    procedure_a = Procedure('test://a')
    procedure_b = Procedure('test://b')
    procedure_c = Procedure('test://c')
    procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}

    expected = [
        create_empty_procedure_summary(1, 'test://a'),
        create_empty_procedure_summary(2, 'test://b'),
        create_empty_procedure_summary(3, 'test://c')
    ]

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value
        # the manager's procedures attribute holds created procedures and is
        # used for retrieval
        instance.procedures = procedures

        service = ScriptExecutionService()
        returned = service.summarise()

        assert returned == expected


def test_ses_stop_calls_process_manager_function():
    """
    Verify that ScriptExecutionService.stop() calls the appropriate domain
    object methods for stopping process execution """

    cmd = StopProcessCommand(process_uid=3)

    with mock.patch('oet.procedure.application.application.domain.ProcessManager') as mock_pm:
        # get the mock ProcessManager instance
        instance = mock_pm.return_value

        service = ScriptExecutionService()
        service.stop(cmd)

        # service should call stop()
        instance.stop.assert_called_once_with(cmd.process_uid)

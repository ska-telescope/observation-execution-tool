# pylint: disable=W0212
# - W0212(protected-access) - tests need to access protected props
"""
Unit tests for the ska_oso_oet.procedure.application module.
"""

import unittest.mock as mock
from unittest.mock import patch, MagicMock
import pytest
import time

from ska_oso_oet.procedure.application.application import (
    PrepareProcessCommand,
    ScriptExecutionService,
    StartProcessCommand,
    StopProcessCommand,
)
from ska_oso_oet.procedure.domain import (
    ArgCapture,
    FileSystemScript,
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

def main(l, item):
    time.sleep(2)
    l.add(item)
"""
    )
    return f"file://{str(script_path)}"


@pytest.fixture
def summary():
    init_args = ProcedureInput(1, 2, a="b", c="d")
    run_args = ProcedureInput(3, 4, e="f", g="h")

    summary = ProcedureSummary(
        id=123,
        script=FileSystemScript("test://test.py"),
        script_args=[ArgCapture(fn="init", fn_args=init_args, time=5),
                     ArgCapture(fn="main", fn_args=run_args, time=8)],
        history=ProcedureHistory([
            (ProcedureState.CREATING, 1),
            (ProcedureState.IDLE, 2),
            (ProcedureState.LOADING, 3),
            (ProcedureState.IDLE, 4),
            (ProcedureState.RUNNING, 5),
            (ProcedureState.IDLE, 6),
            (ProcedureState.COMPLETED, 7)
        ],
            stacktrace=None
        ),
        state=ProcedureState.COMPLETED
    )
    return summary


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
        script=FileSystemScript(script_uri),
        script_args=[ArgCapture(fn="init", fn_args=ProcedureInput(), time=time.time()),
                     ArgCapture(fn="main", fn_args=ProcedureInput(), time=time.time())],
        history=history,
        state=ProcedureState.IDLE,
    )


def test_ses_create_summary_calls_service_correctly(summary):
    """
    Verify that the private method _create_summary calls the
    ProcessManager.summarise function correctly
    """
    with patch("ska_oso_oet.procedure.domain.ProcessManager") as mock_pm:
        mgr = mock_pm.return_value
        mgr.summarise = mock.MagicMock()

        service = ScriptExecutionService()
        service.summarise([123, 456])  # pylint: disable=protected-access

        mgr.summarise.assert_called_once_with([123, 456])


def test_ses_prepare_call_sequence_and_returns_summary_for_created_process(summary):
    """
    Verify that ScriptExecutionService.prepare() calls the appropriate domain
    object methods for process creation and returns the expected summary object
    """
    script = FileSystemScript("test://test.py")
    cmd = PrepareProcessCommand(script=script, init_args=ProcedureInput())

    with patch("ska_oso_oet.procedure.domain.ProcessManager") as mock_pm:
        # get the mock ProcessManager instance
        mgr = mock_pm.return_value
        # tell ProcessManager.create to return PID 123, which is subsequently
        # used for lookup
        mgr.create.return_value = 123
        mgr.summarise = MagicMock(return_value=[summary])

        service = ScriptExecutionService()
        returned = service.prepare(cmd)

        mgr.create.assert_called_once_with(script, init_args=ProcedureInput())
        assert returned == summary


def test_ses_start_calls_process_manager_function_and_returns_summary(summary):
    """
    Verify that ScriptExecutionService.start() calls the appropriate domain
    object methods for starting process execution and returns the expected
    summary object
    """
    cmd = StartProcessCommand(process_uid=123, fn_name="main", run_args=ProcedureInput(1,2,3))

    with patch("ska_oso_oet.procedure.domain.ProcessManager") as mock_pm:
        # get the mock ProcessManager instance
        mgr = mock_pm.return_value
        mgr.summarise = MagicMock(return_value=[summary])

        service = ScriptExecutionService()
        returned = service.start(cmd)

        # service should call run() and return the summary for the executed
        # procedure
        mgr.run.assert_called_once_with(123, call="main", run_args=ProcedureInput(1, 2, 3))
        assert returned == summary

# REDUNDANT - covered in ProcessManager tests
# def test_ses_summarise_returns_summaries_for_requested_pids():
#     """
#     ScriptExecutionService.summarise() should only return status for requested
#     procedures.
#     """
#     procedure_a = Procedure(FileSystemScript("test://a"), procedure_id=1)
#     procedure_b = Procedure(FileSystemScript("test://b"), procedure_id=2)
#     procedure_c = Procedure(FileSystemScript("test://c"), procedure_id=3)
#     procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}
#
#     expected = [
#         create_empty_procedure_summary(1, "test://a", procedure_a.history),
#         create_empty_procedure_summary(3, "test://c", procedure_c.history),
#     ]
#
#     with mock.patch(
#         "ska_oso_oet.procedure.application.application.domain.ProcessManager"
#     ) as mock_pm:
#         # get the mock ProcessManager instance
#         instance = mock_pm.return_value
#         # the manager's procedures attribute holds created procedures and is
#         # used for retrieval
#         instance.procedures = procedures
#
#         service = ScriptExecutionService()
#         returned = service.summarise([1, 3])
#
#         assert returned == expected

# REDUNDANT - covered in ProcessManager tests
# def test_ses_summarise_fails_when_invalid_pid_requested():
#     """
#     Verify that ScriptExecutionService.summarise() fails when an invalid
#     procedure ID is requested.
#     """
#     procedure_a = Procedure(FileSystemScript("test://a"))
#     procedure_b = Procedure(FileSystemScript("test://b"))
#     procedure_c = Procedure(FileSystemScript("test://c"))
#     procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}
#
#     with mock.patch(
#         "ska_oso_oet.procedure.application.application.domain.ProcessManager"
#     ) as mock_pm:
#         # get the mock ProcessManager instance
#         instance = mock_pm.return_value
#         # the manager's procedures attribute holds created procedures and is
#         # used for retrieval
#         instance.procedures = procedures
#
#         service = ScriptExecutionService()
#         with pytest.raises(ValueError):
#             service.summarise([543534])

# REDUNDANT - covered in ProcessManager tests
# def test_ses_summarise_returns_all_summaries_when_no_pid_requested():
#     """
#     Verify that summaries for all procedures are returned when no specific PID
#     is requested.
#     """
#     procedure_a = Procedure(FileSystemScript("test://a"), procedure_id=1)
#     procedure_b = Procedure(FileSystemScript("test://b"), procedure_id=2)
#     procedure_c = Procedure(FileSystemScript("test://c"), procedure_id=3)
#     procedures = {1: procedure_a, 2: procedure_b, 3: procedure_c}
#
#     expected = [
#         create_empty_procedure_summary(1, "test://a", procedure_a.history),
#         create_empty_procedure_summary(2, "test://b", procedure_b.history),
#         create_empty_procedure_summary(3, "test://c", procedure_c.history),
#     ]
#
#     with mock.patch(
#         "ska_oso_oet.procedure.application.application.domain.ProcessManager"
#     ) as mock_pm:
#         # get the mock ProcessManager instance
#         instance = mock_pm.return_value
#         # the manager's procedures attribute holds created procedures and is
#         # used for retrieval
#         instance.procedures = procedures
#
#         service = ScriptExecutionService()
#         returned = service.summarise()
#
#         assert returned == expected


def test_ses_stop_calls_process_manager_function(abort_script):
    """
    Verify that ScriptExecutionService.stop() calls the appropriate
    ProcessManager methods to stop process execution, then prepares and
    starts a new Process running the abort script.
    """
    # Test script/procedures will target sub-array 4
    subarray_id = 4
    # PID of running script
    running_pid = 50
    # PID of new abort Process will be 123
    abort_pid = 123

    # Create Procedure representing the script to be stopped
    procedure_to_stop = Procedure(
        FileSystemScript("test://a"), procedure_id=running_pid, subarray_id=subarray_id
    )

    # Create second Procedure to represent the Process running the
    # post-termination abort script
    abort_procedure = Procedure(
        FileSystemScript(abort_script), procedure_id=abort_pid, subarray_id=subarray_id
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
        script=FileSystemScript(abort_script),
        init_args=abort_procedure.script_args["init"],
    )
    cmd_run = StartProcessCommand(
        process_uid=abort_pid, run_args=abort_procedure.script_args["run"]
    )

    # .. before returning a summary of the running abort Process
    expected = [
        ProcedureSummary(
            id=abort_pid,
            script=abort_procedure.script,
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
            cmd_create.script, init_args=cmd_create.init_args
        )
        instance.run.assert_called_once_with(
            cmd_run.process_uid, run_args=cmd_run.run_args
        )
        assert returned == expected


def test_ses_stop_calls_process_manager_function_with_no_script_execution(abort_script):
    """
    Verify that ScriptExecutionService.stop() calls the appropriate domain
    object methods to stop process execution without executing a subsequent
    abort python script.
    """
    # PID of running process
    running_pid = 123

    cmd = StopProcessCommand(process_uid=running_pid, run_abort=False)

    # returned summary list should be empty if abort script is bypassed
    expected = []

    with patch("ska_oso_oet.procedure.domain.ProcessManager") as mock_pm:
        # get the mock ProcessManager instance
        mgr = mock_pm.return_value
        mgr.create = MagicMock(return_value=12345)
        mgr.stop = MagicMock(return_value='foo')

        service = ScriptExecutionService(abort_script_uri=abort_script)
        returned = service.stop(cmd)

        # service should call stop() and return empty list
        mgr.stop.assert_called_once_with(running_pid)
        mgr.create.assert_not_called()
        assert returned == expected


def test_ses_get_subarray_id_for_requested_pid():
    """
    Verify that the private method _get_subarray_id returns
    subarray id correctly
    """
    subarray_id = 123
    process_pid = 456

    procedure = Procedure(FileSystemScript("test://a"))
    init_args = ProcedureInput(subarray_id=subarray_id)
    procedure.script_args["init"] = init_args
    procedures = {process_pid: procedure}
    process_summary = ProcedureSummary(
        id=process_pid,
        script=procedure.script,
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
    procedure = Procedure(FileSystemScript("test://a"))
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

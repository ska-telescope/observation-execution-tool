"""
Unit tests for the oet.procedure.application.main module.
"""
import multiprocessing as mp
import unittest.mock as mock
from functools import partial

import pytest
from pubsub import pub

from oet.mptools import (
    MPQueue,
    EventMessage
)
from oet.procedure import domain
from oet.procedure.application import application
from oet.procedure.application.main import ScriptExecutionServiceWorker
from tests.oet.mptools.test_mptools import _proc_worker_wrapper_helper

topicMgr = pub.getDefaultTopicMgr()


def test_script_execution_service_worker_verify_list_method_called(caplog):
    """
    SES.summarise should be called when 'request.script.list' message is received
    """
    work_q = MPQueue()
    msg = EventMessage('TEST_SUMMARY', 'PUBSUB', dict(topic='request.script.list', kwargs={'request_id': '123'}))
    work_q.put(msg)
    event = mp.Event()

    with mock.patch('oet.procedure.application.main.ScriptExecutionService.summarise') as mock_cls:
        mock_cls.side_effect = partial(set_event, event)
        _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)

        assert event.is_set() is True
        mock_cls.assert_called_once()
        assert topicMgr.getTopic('script.pool.list')


def test_script_execution_service_worker_verify_start_method_called(caplog):
    """
    SES.start should be called when 'request.script.started' message is received
    """
    cmd = application.StartProcessCommand(process_uid=123, run_args=domain.ProcedureInput())
    with mock.patch('oet.procedure.application.main.ScriptExecutionService.start') as mock_method:
        assert_command_request_and_response(caplog, mock_method, 'request.script.start', 'script.lifecycle.started',
                                            cmd)


def test_script_execution_service_worker_verify_prepare_method_called(caplog):
    """
    SES.prepare should be called when 'request.script.create' message is received
    """
    cmd = application.PrepareProcessCommand(script_uri='test:///hi', init_args=domain.ProcedureInput())
    with mock.patch('oet.procedure.application.main.ScriptExecutionService.prepare') as mock_method:
        assert_command_request_and_response(caplog, mock_method, 'request.script.create', 'script.lifecycle.created',
                                            cmd)


def test_script_execution_service_worker_verify_stop_method_called(caplog):
    """
    SES.stop should be called when 'request.script.stop' message is received
    """
    cmd = application.StopProcessCommand(process_uid=123, run_abort=False)
    with mock.patch('oet.procedure.application.main.ScriptExecutionService.stop') as mock_method:
        assert_command_request_and_response(caplog, mock_method, 'request.script.stop', 'script.lifecycle.stopped', cmd)


def assert_command_request_and_response(caplog, mock_method, request_topic, response_topic, cmd):
    work_q = MPQueue()
    msg = EventMessage('UNITTEST', 'PUBSUB',
                       dict(topic=request_topic, kwargs={'request_id': '1234', 'cmd': cmd}))
    work_q.put(msg)
    event = mp.Event()

    mock_method.side_effect = partial(set_event, event)
    _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)

    assert event.is_set()
    mock_method.assert_called_once()
    assert mock_method.call_args[0][0] == cmd

    assert topicMgr.getTopic(response_topic)


def set_event(event, *args, **kwargs):
    event.set()

"""
Unit tests for the Main module.
"""
import pytest
import unittest.mock as mock
import multiprocessing as mp
from oet.mptools import (
    MPQueue,
    EventMessage
)
from tests.oet.mptools.test_mptools import _proc_worker_wrapper_helper
from oet.procedure.application.main import ScriptExecutionServiceWorker
from oet.procedure import domain
from oet.procedure.application import application
from pubsub import pub

topicMgr = pub.getDefaultTopicMgr()


def test_script_execution_service_worker_verify_list_method_called(caplog):
    work_q = MPQueue()
    msg = EventMessage('TEST_SUMMARY', 'PUBSUB', dict(topic='request.script.list', kwargs={'request_id': '123'}))
    work_q.put(msg)
    event = mp.Event()

    def summarise(*args, **kwargs):
        # these contains the args/kwargs that were supplied to ses.summarise
        event.set()

    with mock.patch('oet.procedure.application.main.ScriptExecutionService.summarise') as mock_cls:
        mock_cls.side_effect = summarise
        _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)
    # grace time is not needed as test runs in main process
    # event.wait(1)
    assert event.is_set() is True
    assert mock_cls.call_count == 1
    mock_cls.assert_called_once()
    assert topicMgr.getTopic('script.pool.list')


def test_script_execution_service_worker_verify_start_method_called(caplog):
    work_q = MPQueue()
    start_cmd = application.StartProcessCommand(process_uid=123, run_args=domain.ProcedureInput())
    msg = EventMessage('TEST_START', 'PUBSUB',
                       dict(topic='request.script.start', kwargs={'request_id': '1234', 'cmd': start_cmd}))
    work_q.put(msg)
    event = mp.Event()

    def start(*args, **kwargs):
        # these contains the args/kwargs that were supplied to ses.start
        event.set()

    with mock.patch('oet.procedure.application.main.ScriptExecutionService.start') as mock_cls:
        mock_cls.side_effect = start
        _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)
    # grace time is not needed as test runs in main process
    # event.wait(1)
    assert event.is_set() is True
    assert mock_cls.call_count == 1
    assert isinstance(mock_cls.call_args[0][0], application.StartProcessCommand)
    start_cmd == mock_cls.call_args[0][0]
    mock_cls.call_args[0][0].process_uid = 123
    mock_cls.assert_called_once()
    assert topicMgr.getTopic('script.lifecycle.started')


def test_script_execution_service_worker_verify_prepare_method_called(caplog):
    work_q = MPQueue()
    prepare_cmd = application.PrepareProcessCommand(script_uri='test:///hi',
                                                    init_args=domain.ProcedureInput())
    msg = EventMessage('TEST_CREATE', 'PUBSUB',
                       dict(topic='request.script.create', kwargs={'request_id': '1234', 'cmd': prepare_cmd}))
    work_q.put(msg)
    event = mp.Event()

    def prepare(*args, **kwargs):
        # these contains the args/kwargs that were supplied to ses.prepare
        event.set()

    with mock.patch('oet.procedure.application.main.ScriptExecutionService.prepare') as mock_cls:
        mock_cls.side_effect = prepare
        _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)
    # grace time is not needed as test runs in main process
    # event.wait(1)
    assert event.is_set() is True
    assert mock_cls.call_count == 1
    assert isinstance(mock_cls.call_args[0][0], application.PrepareProcessCommand)
    prepare_cmd == mock_cls.call_args[0][0]
    mock_cls.call_args[0][0].script_uri = 'test:///hi'
    mock_cls.assert_called_once()
    assert topicMgr.getTopic('script.lifecycle.created')


def test_script_execution_service_worker_verify_stop_method_called(caplog):
    work_q = MPQueue()
    stop_cmd = application.StopProcessCommand(process_uid=123, run_abort=False)
    msg = EventMessage('TEST_STOP', 'PUBSUB',
                       dict(topic='request.script.stop', kwargs={'request_id': '1234', 'cmd': stop_cmd}))
    work_q.put(msg)
    event = mp.Event()

    def stop(*args, **kwargs):
        # these contains the args/kwargs that were supplied to ses.stop
        event.set()

    with mock.patch('oet.procedure.application.main.ScriptExecutionService.stop') as mock_cls:
        mock_cls.side_effect = stop
        _proc_worker_wrapper_helper(caplog, ScriptExecutionServiceWorker, args=(work_q,), expect_shutdown_evt=True)
    # grace time is not needed as test runs in main process
    # event.wait(1)
    assert event.is_set() is True
    assert mock_cls.call_count == 1
    assert isinstance(mock_cls.call_args[0][0], application.StopProcessCommand)
    stop_cmd == mock_cls.call_args[0][0]
    mock_cls.call_args[0][0].process_uid = 123
    mock_cls.assert_called_once()
    assert topicMgr.getTopic('script.lifecycle.stopped')
# BTN-1394
# pylint: disable=W0613
# - W0613(unused-argument): fixture usage
"""
Unit tests for the ska_oso_oet.procedure.application.main module.
"""
import multiprocessing as mp
import unittest.mock as mock
from functools import partial

import pubsub.pub
import pytest

from ska_oso_oet.event import topics
from ska_oso_oet.mptools import EventMessage, MPQueue
from ska_oso_oet.procedure import domain
from ska_oso_oet.procedure.application import application
from ska_oso_oet.procedure.application.main import (
    EventBusWorker,
    FlaskWorker,
    ScriptExecutionServiceWorker,
    main_loop,
)
from tests.unit.ska_oso_oet.mptools.test_mptools import _proc_worker_wrapper_helper
from tests.unit.ska_oso_oet.procedure.application.test_restserver import PubSubHelper

multiprocessing_contexts = [
    mp.get_context("spawn"),
    mp.get_context("fork"),
    mp.get_context("forkserver"),
]


class TestEventBusWorker:
    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_external_messages_are_published_locally(self, mp_fixture, caplog):
        """
        Verify that message event is published if the event originates from an
        external source.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "EXTERNAL COMPONENT",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )
        work_q.put(msg)

        with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
            _proc_worker_wrapper_helper(
                mp_fixture,
                caplog,
                EventBusWorker,
                args=(work_q,),
                expect_shutdown_evt=True,
            )

        assert topics.request.procedure.list in helper.topic_list
        work_q.safe_close()

    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_internal_messages_not_republished(self, mp_fixture, caplog):
        """
        Verify that message event is not published if the event originates from
        an internal source.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        # TEST is the default component name assigned in
        # _proc_worker_wrapper_helper. This message should be ignored.
        msg = EventMessage(
            "TEST",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )

        work_q.put(msg)
        # But coming from NONTEST, this message should be republished.
        msg = EventMessage(
            "NONTEST",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "456"}),
        )
        work_q.put(msg)

        with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
            _proc_worker_wrapper_helper(
                mp_fixture,
                caplog,
                EventBusWorker,
                args=(work_q,),
                expect_shutdown_evt=True,
            )

        assert len(helper.messages) == 1
        assert helper.messages[0][1] == dict(msg_src="NONTEST", request_id="456")

        work_q.safe_close()


class TestScriptExecutionWorker:
    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_list_method_called(self, mp_fixture, caplog):
        """
        SES.summarise should be called when 'request.procedure.list' message is received
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "TEST_SUMMARY",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )
        work_q.put(msg)
        event = mp_fixture.Event()

        with mock.patch(
            "ska_oso_oet.procedure.application.main.ScriptExecutionService.summarise"
        ) as mock_cls:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_cls.side_effect = partial(set_event, event)
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ScriptExecutionServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        assert event.is_set() is True
        mock_cls.assert_called_once()

        assert helper.topic_list == [
            topics.request.procedure.list,  # list requested
            topics.procedure.pool.list,  # response published
        ]

        work_q.safe_close()

    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_handles_request_to_list_invalid_id(self, mp_fixture, caplog):
        """
        The ValueError raised when SES.summarise is given an invalid PID should be handled.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "TEST_SUMMARY",
            "PUBSUB",
            dict(topic=topics.request.procedure.list, kwargs={"request_id": "123"}),
        )
        work_q.put(msg)

        with mock.patch(
            "ska_oso_oet.procedure.application.main.ScriptExecutionService.summarise"
        ) as mock_cls:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_cls.side_effect = ValueError
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ScriptExecutionServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        mock_cls.assert_called_once()

        assert helper.topic_list == [
            topics.request.procedure.list,  # list requested
            topics.procedure.pool.list,  # response published
        ]
        assert helper.messages[1][1] == dict(
            msg_src="TEST", request_id="123", result=[]
        )

        work_q.safe_close()

    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_start_method_called(self, mp_fixture, caplog):
        """
        SES.start should be called when 'request.procedure.start' message is received
        """
        cmd = application.StartProcessCommand(
            process_uid=123, fn_name="main", run_args=domain.ProcedureInput()
        )
        with mock.patch(
            "ska_oso_oet.procedure.application.main.ScriptExecutionService.start"
        ) as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                mock_method,
                topics.request.procedure.start,
                topics.procedure.lifecycle.started,
                cmd,
            )

    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_prepare_method_called(self, mp_fixture, caplog):
        """
        SES.prepare should be called when 'request.procedure.create' message is received
        """
        cmd = application.PrepareProcessCommand(
            script=domain.FileSystemScript("file:///hi"),
            init_args=domain.ProcedureInput(),
        )
        with mock.patch(
            "ska_oso_oet.procedure.application.main.ScriptExecutionService.prepare"
        ) as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                mock_method,
                topics.request.procedure.create,
                topics.procedure.lifecycle.created,
                cmd,
            )

    @pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
    def test_stop_method_called(self, mp_fixture, caplog):
        """
        SES.stop should be called when 'request.procedure.stop' message is received
        """
        cmd = application.StopProcessCommand(process_uid=123, run_abort=False)
        with mock.patch(
            "ska_oso_oet.procedure.application.main.ScriptExecutionService.stop"
        ) as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                mock_method,
                topics.request.procedure.stop,
                topics.procedure.lifecycle.stopped,
                cmd,
            )


def assert_command_request_and_response(
    mp_fixture, caplog, mock_method, request_topic, response_topic, cmd
):
    pubsub.pub.unsubAll()
    helper = PubSubHelper()

    work_q = MPQueue(ctx=mp_fixture)
    msg = EventMessage(
        "UNITTEST",
        "PUBSUB",
        dict(topic=request_topic, kwargs={"request_id": "1234", "cmd": cmd}),
    )
    work_q.put(msg)
    event = mp_fixture.Event()

    mock_method.side_effect = partial(set_event, event)
    with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
        _proc_worker_wrapper_helper(
            mp_fixture,
            caplog,
            ScriptExecutionServiceWorker,
            args=(work_q, mp_fixture),
            expect_shutdown_evt=True,
        )

    assert event.is_set()
    mock_method.assert_called_once()
    assert mock_method.call_args[0][0] == cmd

    assert helper.topic_list == [request_topic, response_topic]

    work_q.safe_close()


def set_event(event, *args, **kwargs):
    """
    Set given multiprocessing.Event.
    """
    event.set()


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_flask_worker_starts_flask(mp_fixture, caplog):
    """
    Verify that the FlaskWorker starts Flask.
    """
    with mock.patch("flask.Flask") as mock_flask:
        # mock Flask causes connection error in shutdown as shutdown URL is accessed
        with mock.patch("requests.post"):
            _proc_worker_wrapper_helper(
                mp_fixture,
                caplog,
                FlaskWorker,
                args=(MPQueue(ctx=mp_fixture),),
                expect_shutdown_evt=True,
            )

        mock_app_instance = mock_flask.return_value
        mock_app_instance.run.assert_called_once()


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_ends_when_shutdown_event_is_set(mp_fixture):
    """
    Main loop should terminate when shutdown event is set.
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "END", msg="foo"))
    mock_ctx.event_queue = event_q

    # one processing loop before shutdown in set, at which point the loop
    # should exit with two messages still in the event queue
    mock_ctx.shutdown_event.is_set.side_effect = [False, False, True]

    main_loop(mock_ctx, [])

    assert event_q.safe_close() == 2


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_ends_on_end_message(mp_fixture):
    """
    Main loop should terminate when end message is received.
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="foo"))
    event_q.put(EventMessage("TEST", "END", msg="foo"))
    mock_ctx.event_queue = event_q

    mock_ctx.shutdown_event.is_set.return_value = False

    main_loop(mock_ctx, [])

    assert event_q.safe_close() == 0


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_adds_pubsub_messages_to_event_queues(mp_fixture):
    """
    PUBSUB messages should be added to event queues.
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    event_q.put(EventMessage("TEST", "PUBSUB", msg="1"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="2"))
    event_q.put(EventMessage("TEST", "PUBSUB", msg="3"))
    event_q.put(EventMessage("TEST", "END", msg="foo"))
    mock_ctx.event_queue = event_q

    # one processing loop before shutdown in set, at which point the loop
    # should exit with three messages still in the event queue
    mock_ctx.shutdown_event.is_set.return_value = False

    q1 = MPQueue(ctx=mp_fixture)
    q2 = MPQueue(ctx=mp_fixture)

    main_loop(mock_ctx, [q1, q2])

    assert q1.safe_close() == 3
    assert q2.safe_close() == 3

    event_q.safe_close()


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_ignores_and_logs_events_of_unknown_types(mp_fixture):
    """
    Loop should log events it doesn't know how to handle.
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    event_q.put(EventMessage("TEST", "FOO", msg="1"))
    mock_ctx.event_queue = event_q

    # one processing loop before shutdown in set, at which point the loop
    # should exit with three messages still in the event queue
    mock_ctx.shutdown_event.is_set.side_effect = [False, True]

    main_loop(mock_ctx, [])

    event_q.safe_close()
    mock_ctx.log.assert_called_once()
    assert "Unknown Event" in mock_ctx.log.call_args[0][1]


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_checks_shutdown_event_after_every_queue_get(mp_fixture):
    """
    Loop should regularly check shutdown event,
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    mock_ctx.event_queue.safe_get.side_effect = [
        False,
        False,
        EventMessage("TEST", "END", msg="foo"),
    ]

    # loop won't exit as a result of shutdown_event being True
    mock_ctx.shutdown_event.is_set.side_effect = [False, False, False, False, False]

    main_loop(mock_ctx, [])

    assert event_q.safe_close() == 0
    assert mock_ctx.shutdown_event.is_set.call_count == 3


@pytest.mark.parametrize("mp_fixture", multiprocessing_contexts)
def test_main_loop_ends_on_fatal_message(mp_fixture):
    """
    Main loop should terminate when fatal messsage is received.
    """
    mock_ctx = mock.MagicMock()

    event_q = MPQueue(ctx=mp_fixture)
    event_q.put(EventMessage("TEST", "FATAL", msg="foo"))
    event_q.put(EventMessage("TEST", "END", msg="foo"))
    mock_ctx.event_queue = event_q

    mock_ctx.shutdown_event.is_set.return_value = False

    main_loop(mock_ctx, [])

    assert event_q.safe_close() == 1

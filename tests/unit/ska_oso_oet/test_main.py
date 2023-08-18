# pylint: disable=W0613
# - W0613(unused-argument): fixture usage
"""
Unit tests for the ska_oso_oet.main module.
"""
import unittest.mock as mock
from functools import partial

import pubsub.pub

import ska_oso_oet.activity.application
from ska_oso_oet.event import topics
from ska_oso_oet.main import (
    ActivityServiceWorker,
    EventBusWorker,
    FlaskWorker,
    ScriptExecutionServiceWorker,
    main_loop,
)
from ska_oso_oet.mptools import EventMessage, MPQueue
from ska_oso_oet.procedure import application, domain
from tests.unit.ska_oso_oet.mptools.test_mptools import _proc_worker_wrapper_helper

from .test_ui import PubSubHelper


class TestEventBusWorker:
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
            "ska_oso_oet.main.ScriptExecutionService.summarise"
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
            "ska_oso_oet.main.ScriptExecutionService.summarise"
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

    def test_start_method_called(self, mp_fixture, caplog):
        """
        SES.start should be called when 'request.procedure.start' message is received
        """
        cmd = application.StartProcessCommand(
            process_uid=123, fn_name="main", run_args=domain.ProcedureInput()
        )
        with mock.patch("ska_oso_oet.main.ScriptExecutionService.start") as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                ScriptExecutionServiceWorker,
                mock_method,
                topics.request.procedure.start,
                topics.procedure.lifecycle.started,
                cmd,
            )

    def test_prepare_method_called(self, mp_fixture, caplog):
        """
        SES.prepare should be called when 'request.procedure.create' message is received
        """
        cmd = application.PrepareProcessCommand(
            script=domain.FileSystemScript("file:///hi"),
            init_args=domain.ProcedureInput(),
        )
        with mock.patch(
            "ska_oso_oet.main.ScriptExecutionService.prepare"
        ) as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                ScriptExecutionServiceWorker,
                mock_method,
                topics.request.procedure.create,
                topics.procedure.lifecycle.created,
                cmd,
            )

    def test_stop_method_called(self, mp_fixture, caplog):
        """
        SES.stop should be called when 'request.procedure.stop' message is received
        """
        cmd = application.StopProcessCommand(process_uid=123, run_abort=False)
        with mock.patch("ska_oso_oet.main.ScriptExecutionService.stop") as mock_method:
            assert_command_request_and_response(
                mp_fixture,
                caplog,
                ScriptExecutionServiceWorker,
                mock_method,
                topics.request.procedure.stop,
                topics.procedure.lifecycle.stopped,
                cmd,
            )


class TestActivityWorker:
    def test_list_method_called(self, mp_fixture, caplog):
        """
        ActivityService.summarise should be called when 'topics.request.activity.list' message is received.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "TEST_SUMMARISE",
            "PUBSUB",
            dict(
                topic=topics.request.activity.list,
                kwargs={"request_id": "678", "activity_ids": ["0987"]},
            ),
        )
        work_q.put(msg)
        event = mp_fixture.Event()

        with mock.patch("ska_oso_oet.main.ActivityService.summarise") as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.side_effect = partial(set_event, event)
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        assert event.is_set() is True
        mock_method.assert_called_once_with(["0987"])

        assert helper.topic_list == [
            topics.request.activity.list,  # list requested
            topics.activity.pool.list,  # response published
        ]

        work_q.safe_close()

    def tests_handles_request_to_list_handles_invalid_id(self, mp_fixture, caplog):
        """
        A ValueError raised by ActivityService.summarise should be handled by the worker
        and an empty list returned.
        """

        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "TEST_SUMMARY",
            "PUBSUB",
            dict(topic=topics.request.activity.list, kwargs={"request_id": "678"}),
        )
        work_q.put(msg)

        with mock.patch("ska_oso_oet.main.ActivityService.summarise") as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.side_effect = ValueError
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        mock_method.assert_called_once()

        assert helper.topic_list == [
            topics.request.activity.list,  # list requested
            topics.activity.pool.list,  # response published
        ]

        assert helper.messages[1][1] == dict(
            msg_src="TEST", request_id="678", result=[]
        )

        work_q.safe_close()

    def test_prepare_method_called(self, mp_fixture, caplog):
        """
        ActivityService.prepare_run_activity should be called when 'topics.request.activity.run' message is received.
        For the happy path, a response message shouldn't be sent.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()
        cmd = ska_oso_oet.activity.application.ActivityCommand(
            "test_activity", "sbd-123", False, False, {}
        )

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "UNITTEST",
            "PUBSUB",
            dict(
                topic=topics.request.activity.run,
                kwargs={"request_id": "123", "cmd": cmd},
            ),
        )
        work_q.put(msg)
        event = mp_fixture.Event()

        with mock.patch(
            "ska_oso_oet.main.ActivityService.prepare_run_activity"
        ) as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.side_effect = partial(set_event, event)
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

            assert event.is_set()
            mock_method.assert_called_once()
            assert mock_method.call_args[0][0] == cmd

            assert helper.topic_list == [topics.request.activity.run]

            work_q.safe_close()

    def test_prepare_handles_error(self, mp_fixture, caplog):
        """
        An exception raised by ActivityService.prepare_run_activity should be handled by the worker by sending
        a message to the response topic with the error.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        cmd = ska_oso_oet.activity.application.ActivityCommand(
            "test_activity", "sbd-123", False, False, {}
        )
        msg = EventMessage(
            "TEST_SUMMARY",
            "PUBSUB",
            dict(
                topic=topics.request.activity.run,
                kwargs={"request_id": "678", "cmd": cmd},
            ),
        )
        work_q.put(msg)
        expected_error = RuntimeError("test error")

        with mock.patch(
            "ska_oso_oet.main.ActivityService.prepare_run_activity"
        ) as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.side_effect = expected_error
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        mock_method.assert_called_once()

        assert helper.topic_list == [
            topics.request.activity.run,  # list requested
            topics.activity.lifecycle.running,  # response published
        ]

        assert helper.messages[1][1] == dict(
            msg_src="TEST", request_id="678", result=expected_error
        )

        work_q.safe_close()

    def test_complete_method_called(self, mp_fixture, caplog):
        """
        ActivityService.complete_run_activity should be called when 'topics.procedure.lifecycle.created' message is received,
        and a response message sent to 'topics.activity.lifecycle.running' with the ActivitySummary
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        procedure_summary = application.ProcedureSummary(1, None, None, None, None)

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "UNITTEST",
            "PUBSUB",
            dict(
                topic=topics.procedure.lifecycle.created,
                kwargs={"request_id": "123", "result": procedure_summary},
            ),
        )
        work_q.put(msg)
        expected_activity_summary = ska_oso_oet.activity.application.ActivitySummary(
            1, 2, "sbd-123", "allocate", True, {}, [], "sbi-1234"
        )

        with mock.patch(
            "ska_oso_oet.main.ActivityService.complete_run_activity"
        ) as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.return_value = expected_activity_summary
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

            mock_method.assert_called_once()
            assert mock_method.call_args[0][0] == procedure_summary

            assert helper.topic_list == [
                topics.procedure.lifecycle.created,
                topics.activity.lifecycle.running,
            ]

            activity_summary = helper.messages_on_topic(
                topics.activity.lifecycle.running
            )[0]["result"]

            assert activity_summary == expected_activity_summary
            work_q.safe_close()

    def test_complete_handles_error(self, mp_fixture, caplog):
        """
        An exception raised by ActivityService.complete_run_activity should be handled by the worker by sending
        a message to the response topic with the error.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        work_q = MPQueue(ctx=mp_fixture)
        procedure_summary = application.ProcedureSummary(1, None, None, None, None)
        msg = EventMessage(
            "UNITTEST",
            "PUBSUB",
            dict(
                topic=topics.procedure.lifecycle.created,
                kwargs={"request_id": "123", "result": procedure_summary},
            ),
        )
        work_q.put(msg)
        expected_error = RuntimeError("test error")

        with mock.patch(
            "ska_oso_oet.main.ActivityService.complete_run_activity"
        ) as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.side_effect = expected_error
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

        mock_method.assert_called_once()

        assert helper.topic_list == [
            topics.procedure.lifecycle.created,
            topics.activity.lifecycle.running,
        ]

        assert helper.messages[1][1] == dict(
            msg_src="TEST", request_id="123", result=expected_error
        )

        work_q.safe_close()

    def test_complete_handle_none_activity_procedure(self, mp_fixture, caplog):
        """
        When ActivityService.complete_run_activity returns None this means the Procedure was not created from an Activity request
        so no response message should be sent.
        """
        pubsub.pub.unsubAll()
        helper = PubSubHelper()

        procedure_summary = application.ProcedureSummary(1, None, None, None, None)

        work_q = MPQueue(ctx=mp_fixture)
        msg = EventMessage(
            "UNITTEST",
            "PUBSUB",
            dict(
                topic=topics.procedure.lifecycle.created,
                kwargs={"request_id": "123", "result": procedure_summary},
            ),
        )
        work_q.put(msg)

        with mock.patch(
            "ska_oso_oet.main.ActivityService.complete_run_activity"
        ) as mock_method:
            with mock.patch.object(pubsub.pub, "unsubAll", return_value=[]):
                mock_method.return_value = None
                _proc_worker_wrapper_helper(
                    mp_fixture,
                    caplog,
                    ActivityServiceWorker,
                    args=(work_q, mp_fixture),
                    expect_shutdown_evt=True,
                )

            mock_method.assert_called_once()
            assert mock_method.call_args[0][0] == procedure_summary

            assert helper.topic_list == [
                topics.procedure.lifecycle.created,
            ]

            assert helper.messages_on_topic(topics.activity.lifecycle.running) == []
            work_q.safe_close()


def assert_command_request_and_response(
    mp_fixture, caplog, worker_cls, mock_method, request_topic, response_topic, cmd
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
            worker_cls,
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


def test_flaskworker_server_lifecycle(mp_fixture, caplog, mocker):
    """
    Verify that the FlaskWorker starts and shuts down the Waitress server.
    """

    with mock.patch("waitress.create_server") as m_server:
        _proc_worker_wrapper_helper(
            mp_fixture,
            caplog,
            FlaskWorker,
            args=(MPQueue(ctx=mp_fixture),),
            expect_shutdown_evt=True,
        )

        mock_app_instance = m_server.return_value
        mock_app_instance.run.assert_called_once()
        mock_app_instance.close.assert_called_once()


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
    assert "Unhandled Event" in mock_ctx.log.call_args[0][1]


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

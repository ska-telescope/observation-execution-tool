# pylint: disable=W0212,W0613
# - W0212(protected-access) - tests need to access protected props
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the procedure REST API module.
"""
import threading
import time
import types
from typing import List
from unittest import mock

import pytest
from httpx import Response
from pubsub import pub
from pydantic import ValidationError
from ska_oso_scripting.event import user_topics

import ska_oso_oet.utils.ui
from ska_oso_oet import mptools
from ska_oso_oet.event import topics
from ska_oso_oet.procedure.domain import ProcedureState
from ska_oso_oet.ui import Message
from ska_oso_oet.ui import messages as sse_messages
from tests.unit.conftest import DEFAULT_API_PATH, PROCEDURES_ENDPOINT


@pytest.fixture(name="short_timeout")
def fixture_short_timeout():
    """
    Fixture to shorten grace period before timeout
    """
    timeout = ska_oso_oet.utils.ui.TIMEOUT

    try:
        ska_oso_oet.utils.ui.TIMEOUT = 0.1
        yield
    finally:
        ska_oso_oet.utils.ui.TIMEOUT = timeout


class PubSubHelper:
    def __init__(self, spec=None, match_request_id=True):
        # client just wants to capture all messages, no responses required
        if spec is None:
            spec = {}

        messages = []
        self.messages = messages
        self.spec = spec
        self.match_request_id = match_request_id
        pub.subscribe(self.respond, pub.ALL_TOPICS)

    def respond(self, topic=pub.AUTO_TOPIC, **msg_data):
        base_topic = topic.name.split(".")[0]
        if getattr(topics, base_topic, None):
            topic_cls = self.get_topic_class(topics, topic.name)
        elif getattr(user_topics, base_topic, None):
            topic_cls = self.get_topic_class(user_topics, topic.name)
        else:
            raise RuntimeError(f"Topic not recognised: {topic.name}")
        self.messages.append((topic, msg_data))

        if topic_cls in self.spec:
            (args, kwargs) = self.spec[topic_cls].pop(0)

            kwargs["msg_src"] = "PubSubHelper"
            if "request_id" in msg_data and self.match_request_id:
                kwargs["request_id"] = msg_data["request_id"]

            pub.sendMessage(*args, **kwargs)

    @property
    def topic_list(self):
        topic_list = [
            self.get_topic_class(topics, topic.name) for (topic, _) in self.messages
        ]
        return topic_list

    def __getitem__(self, key):
        return self.messages[key]

    def get_topic_class(self, module, cls):
        if not cls:
            return module
        s = cls.split(".")
        cls = getattr(module, s[0])
        return self.get_topic_class(cls, ".".join(s[1:]))

    def messages_on_topic(self, topic):
        return [
            msg
            for msg_topic, msg in self.messages
            if msg_topic.name == topic._topicNameStr
        ]

    def wait_for_message_on_topic(self, topic, timeout=1.0, tick=0.01):
        deadline = time.time() + timeout
        sleep_secs = tick
        len_before = len(self.messages_on_topic(topic))
        while len(self.messages_on_topic(topic)) == len_before and sleep_secs > 0:
            time.sleep(sleep_secs)
            sleep_secs = mptools._sleep_secs(tick, deadline)

    def wait_for_lifecycle(self, state, msg_src=None, timeout=1.0, tick=0.01) -> bool:
        """
        Timebound wait for a lifecycle state event to be received signifying a
        transition to the target state.

        Returns True if the event was received.
        """
        deadline = time.time() + timeout
        sleep_secs = tick

        if msg_src is None:

            def msg_src_matcher(m):
                return True

        else:

            def msg_src_matcher(m):
                return m.get("msg_src", None) == str(msg_src)

        def any_msgs_with_state():
            return any(
                True
                for m in self.messages_on_topic(topics.procedure.lifecycle.statechange)
                if m["new_state"] == state and msg_src_matcher(m)
            )

        while not any_msgs_with_state() and sleep_secs > 0:
            time.sleep(sleep_secs)
            sleep_secs = mptools._sleep_secs(tick, deadline)

        return any_msgs_with_state()

    def assert_state_history(self, pid: int, expected: List[ProcedureState]):
        """
        Assert that the state history of a Procedure is as expected.

        :param pid: PID of Procedure to inspect
        :param expected: ordered list of states for comparison
        """
        msgs = self.messages_on_topic(topics.procedure.lifecycle.statechange)
        states = [msg["new_state"] for msg in msgs if int(msg["msg_src"]) == pid]
        assert states == expected

    def assert_state(self, pid: int, expected: ProcedureState):
        """
        Assert that the published state of a Procedure is as expected.

        :param pid: PID of Procedure to inspect
        :param expected: expected state for comparison
        """
        msgs = self.messages_on_topic(topics.procedure.lifecycle.statechange)
        states = [msg["new_state"] for msg in msgs if int(msg["msg_src"]) == pid]
        assert states[-1] == expected


def test_call_and_respond_aborts_with_timeout_when_no_response_received(
    client, short_timeout
):
    """
    HTTP 504 (Gateway Timeout) should be raised when message reception wait
    time exceeds timeout
    """
    # do not prime pubsub, so request will timeout
    response = client.get(PROCEDURES_ENDPOINT)
    # 504 and timeout error message
    assert response.status_code == 504

    response_json = response.json()
    assert response_json["detail"].startswith("Timeout waiting for msg ")


def test_call_and_respond_ignores_responses_when_request_id_differs(client):
    """
    Verify that the messages with different request IDs are ignored.
    """

    # call_and_respond will block the MainThread while waiting for its queue
    # to be filled with a result, hence we need to create another thread which
    # will broadcast messages as if it's the other component running
    # concurrently
    def publish():
        # sleep long enough for call_and_respond to start running
        time.sleep(0.1)
        for i in range(10):
            pub.sendMessage(
                topics.procedure.pool.list, msg_src="mock", request_id=123, result=i
            )
        pub.sendMessage(
            topics.procedure.pool.list, msg_src="mock", request_id=456, result="ok"
        )

    t = threading.Thread(target=publish)

    # this sets the request ID to match to 'bar'
    with mock.patch("time.time_ns") as mock_time:
        mock_time.return_value = 456

        t.start()
        result = ska_oso_oet.utils.ui.call_and_respond(
            topics.request.procedure.list, topics.procedure.pool.list
        )

    assert result == "ok"


def mock_message_encode(data, encoding):
    return bytes(str(data), encoding=encoding)


@pytest.mark.asyncio
@mock.patch("ska_oso_oet.ui.messages")
@mock.patch.object(Message, "encode", new=mock_message_encode, create=True)
async def test_sse_string_messages_are_streamed_correctly(mock_messages, async_client):
    """
    Verify that simple Messages are streamed as SSE events correctly.
    """
    msg = Message(data="foo", type="message")
    mock_messages.return_value = [msg]

    async with async_client:
        response = await async_client.get(f"/{DEFAULT_API_PATH}/stream")

        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        mock_messages.assert_called()
        assert response.text == "\nevent:message\ndata:foo\n\n"


@pytest.mark.asyncio
@mock.patch("ska_oso_oet.ui.messages")
@mock.patch.object(Message, "encode", new=mock_message_encode, create=True)
async def test_sse_complex_messages_are_streamed_correctly(mock_messages, async_client):
    """
    Verify that Messages containing structured data are streamed correctly.
    """
    msg = Message(data={"foo": "bar"}, type="message", id=123)
    mock_messages.return_value = [msg]

    async with async_client:
        response = await async_client.get(f"/{DEFAULT_API_PATH}/stream")

        assert isinstance(response, Response)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        mock_messages.assert_called()
        assert response.text == '\nevent:message\ndata:{"foo": "bar"}\nid:123\n\n'


def test_sse_messages_returns_pubsub_messages():
    """
    Test that pypubsub messages are returned by SSE blueprint's messages method.
    """

    def publish():
        # sleep long enough for generator to start running
        time.sleep(0.1)
        pub.sendMessage(topics.sb.lifecycle.started, msg_src="foo", sbi_id="bar")

    t = threading.Thread(target=publish)

    gen = sse_messages(shutdown_event=threading.Event())
    assert isinstance(gen, types.GeneratorType)

    t.start()

    output = next(gen)
    assert output == Message(
        data=dict(topic="sb.lifecycle.started", msg_src="foo", sbi_id="bar")
    )


def test_message_str():
    """
    Verify that the str string for a Message is correctly formatted.
    """
    message = Message(data="foo", type="message", id=123, retry=100)
    assert str(message) == "event:message\ndata:foo\nid:123\nretry:100\n\n"


def test_message_with_multiline_data():
    """
    Verify that message works with multiline data.
    """
    message = Message(data="foo\nbar")
    assert message.data == "foo\nbar"
    assert message.type is None
    assert message.id is None
    assert message.retry is None
    assert str(message) == "data:foo\ndata:bar\n\n"


def test_message_raise_exception_on_empty():
    """
    Verify that empty message() raise exception
    """
    with pytest.raises(ValidationError):
        Message()


def test_message_with_simple_data():
    """
    Verify that message works with simple data.
    """
    message = Message(data="foo")
    assert message.data == "foo"
    assert message.type is None
    assert message.id is None
    assert message.retry is None
    assert str(message) == "data:foo\n\n"

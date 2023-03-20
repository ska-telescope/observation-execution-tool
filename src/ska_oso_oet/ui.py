"""
The ska_oso_oet.ui package contains code that present the OET interface to the
outside world. In practical terms, this means the OET application's REST
interface
"""
import json
import multiprocessing
from typing import Generator, Optional, Union

import flask
import jsonpickle
from flask import Blueprint, current_app, stream_with_context
from pubsub import pub

from ska_oso_oet.activity.ui import ActivityAPI
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure.ui import ProcedureAPI


class Message:
    """
    Data that is published as a server-sent event.
    """

    def __init__(
        self,
        data: Union[str, dict],
        type: Optional[str] = None,  # pylint: disable=redefined-builtin
        id: Optional[  # pylint: disable=redefined-builtin
            Union[float, int, str]
        ] = None,
        retry: Optional[int] = None,
    ):
        """
        Create a server-sent event.

        :param data: The event data.
        :param type: An optional event type.
        :param id: An optional event ID.
        :param retry: An optional integer, to specify the reconnect time for
            disconnected clients of this stream.
        """
        self.data = data
        self.type = type
        self.id = id
        self.retry = retry

    def __str__(self):
        """
        Serialize this object to a string, according to the `server-sent events
        specification <https://www.w3.org/TR/eventsource/>`_.
        """
        if isinstance(self.data, dict):
            data = jsonpickle.dumps(self.data)
        else:
            data = self.data
        lines = ["data:{value}".format(value=line) for line in data.splitlines()]
        if self.type:
            lines.insert(0, "event:{value}".format(value=self.type))
        if self.id:
            lines.append("id:{value}".format(value=self.id))
        if self.retry:
            lines.append("retry:{value}".format(value=self.retry))
        return "\n".join(lines) + "\n\n"

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and self.data == other.data
            and self.type == other.type
            and self.id == other.id
            and self.retry == other.retry
        )


class ServerSentEventsBlueprint(Blueprint):
    """
    A :class:`flask.Blueprint` subclass that knows how to subscribe to pypubsub
    topics and stream pubsub events as server-sent events.
    """

    def __init__(self, *args, mp_context=None, **kwargs):
        super().__init__(*args, **kwargs)
        if mp_context is None:
            mp_context = multiprocessing.get_context()
        self._mp_context = mp_context

    def messages(self) -> Generator[Message, None, None]:
        """
        A generator of Message objects created from received pubsub events
        """
        q = MPQueue(ctx=self._mp_context)

        def add_to_q(topic: pub.Topic = pub.AUTO_TOPIC, **kwargs):
            kwargs["topic"] = topic.name
            other = {}
            if "request_id" in kwargs:
                other["id"] = kwargs["request_id"]
                del kwargs["request_id"]

            msg = Message(kwargs, **other)
            q.put(msg)

        pub.subscribe(add_to_q, pub.ALL_TOPICS)

        shutdown_event = current_app.config["shutdown_event"]
        while not shutdown_event.is_set():
            msg = q.safe_get(timeout=0.1)
            if msg is not None:
                yield msg

    def stream(self) -> flask.Response:
        @stream_with_context
        def generator():
            # must immediately yield to return 200 OK response to client,
            # otherwise response is only sent on first event
            yield "\n"
            for message in self.messages():
                yield str(message)

        return current_app.response_class(generator(), mimetype="text/event-stream")


@ProcedureAPI.errorhandler(400)
@ProcedureAPI.errorhandler(404)
@ProcedureAPI.errorhandler(500)
@ProcedureAPI.errorhandler(504)
@ActivityAPI.errorhandler(400)
@ActivityAPI.errorhandler(404)
@ActivityAPI.errorhandler(500)
@ActivityAPI.errorhandler(504)
def server_error_response(cause):
    """
    Custom error handler for Procedure API.
    This is overloaded for 400, 404, 500 and 504 and could conceivably be
    extended for other errors by adding the appropriate errorhander decorator.

    :param cause: root exception for failure (e.g., KeyError)
    :return: HTTP Response
    """
    response = cause.get_response()
    if isinstance(cause.description, dict):
        response_data = {
            "error": f"{cause.code} {cause.name}",
            "type": cause.description["type"],
            "Message": cause.description["Message"],
        }
    else:
        response_data = {
            "error": f"{cause.code} {cause.name}",
            "type": cause.name,
            "Message": cause.description,
        }
    response.content_type = "application/json"
    response.data = json.dumps(response_data)
    return response


# def create_app(config_filename):
def create_app():
    """
    Create and return a new Flask app that will serve the REST API.
    """
    app = flask.Flask(__name__)
    # TODO get application config working
    # app.config.from_pyfile(config_filename)

    app.register_blueprint(ProcedureAPI, url_prefix="/api/v1.0", name="procedures")
    app.register_blueprint(ActivityAPI, url_prefix="/api/v1.0", name="activities")

    sse = ServerSentEventsBlueprint("sse", __name__)
    sse.add_url_rule(rule="", endpoint="stream", view_func=sse.stream)
    app.register_blueprint(sse, url_prefix="/api/v1.0/stream")

    app.config.update(msg_src=__name__)

    return app

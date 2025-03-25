"""
The ska_oso_oet.ui package contains code that present the OET interface to the
outside world. In practical terms, this means the OET application's REST
interface
"""
import multiprocessing
import os
from http import HTTPStatus
from typing import Any, Dict, Generator, Optional, Union

import flask
import jsonpickle
import prance
from connexion import App
from fastapi import FastAPI, HTTPException, Request
from flask import Blueprint, current_app, stream_with_context
from pubsub import pub
from werkzeug.exceptions import GatewayTimeout

from ska_oso_oet.activity.ui import activities_router
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure.ui import procedures_router
from ska_oso_oet.utils.ui import API_PATH


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


def get_openapi_spec() -> Dict[str, Any]:
    "Parses and Returns OpenAPI spec"
    cwd, _ = os.path.split(__file__)
    path = os.path.join(cwd, "./openapi/oet-openapi-v1.yaml")
    parser = prance.ResolvingParser(path, lazy=True, strict=True)
    parser.parse()
    spec = parser.specification
    return spec


def create_app(open_api_spec=None):
    "Returns Flask App using Connexion"
    if open_api_spec is None:
        open_api_spec = get_openapi_spec()

    connexion = App(__name__, specification_dir="openapi/")

    connexion.app.config.update(msg_src=__name__)
    # TODO: Due to the limitation of Swagger Open API, we kept the same earlier blueprint approach for Stream API and couldn't include it in the open API spec, we can plan this work when full SSE support is available in OPEN API 3.0 or any latest version.
    sse = ServerSentEventsBlueprint("sse", __name__)
    sse.add_url_rule(rule="", endpoint="stream", view_func=sse.stream)
    connexion.app.register_blueprint(sse, url_prefix=f"{API_PATH}/stream")

    return connexion.app


async def timeout_handler(_: Request, err: GatewayTimeout) -> HTTPException:
    """
    A custom handler function to deal with GatewayTimeout and
    return the correct HTTP response.
    """
    return HTTPException(
        status_code=HTTPStatus.GATEWAY_TIMEOUT,
        detail=err.description["Message"],
    )


def create_fastapi_app():
    app = FastAPI(
        openapi_url=f"{API_PATH}/openapi.json",
        docs_url=f"{API_PATH}/ui",
    )
    app.include_router(activities_router, prefix=API_PATH)
    app.include_router(procedures_router, prefix=API_PATH)
    # app.include_router(sse_router, prefix=API_PATH)

    app.exception_handler(GatewayTimeout)(timeout_handler)

    return app

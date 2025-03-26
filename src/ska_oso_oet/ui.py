"""
The ska_oso_oet.ui package contains code that present the OET interface to the
outside world. In practical terms, this means the OET application's REST
interface
"""
import json
import multiprocessing
import os
from http import HTTPStatus
from threading import Event
from typing import Any, Dict, Generator, Optional, Union

import prance
from connexion import App
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pubsub import pub
from pydantic import BaseModel
from werkzeug.exceptions import GatewayTimeout

from ska_oso_oet.activity.ui import activities_router
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure.ui import procedures_router
from ska_oso_oet.utils.ui import API_PATH

sse_router = APIRouter()


def serialize(obj):
    if isinstance(obj, BaseModel):
        return obj.model_dump()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


class Message(BaseModel):
    """
    Data that is published as a server-sent event.
    """

    data: Union[str, dict]
    type: Optional[str] = None  # pylint: disable=redefined-builtin
    id: Optional[Union[float, int, str]] = None  # pylint: disable=redefined-builtin
    retry: Optional[int] = None

    def __str__(self):
        """
        Serialize this object to a string, according to the `server-sent events
        specification <https://www.w3.org/TR/eventsource/>`_.
        """
        if isinstance(self.data, dict):
            data = json.dumps(self.data, default=serialize)
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


def messages(shutdown_event: Event) -> Generator[Message, None, None]:
    """
    A generator of Message objects created from received pubsub events
    """
    mp_context = multiprocessing.get_context()
    q = MPQueue(ctx=mp_context)

    def add_to_q(topic: pub.Topic = pub.AUTO_TOPIC, **kwargs):
        kwargs["topic"] = topic.name
        if "request_id" in kwargs:
            request_id = kwargs["request_id"]
            del kwargs["request_id"]
            msg = Message(data=kwargs, id=request_id)
        else:
            msg = Message(data=kwargs)

        q.put(msg)

    pub.subscribe(add_to_q, pub.ALL_TOPICS)

    # shutdown_event = current_app.config["shutdown_event"]
    # while not shutdown_event.is_set():
    while not shutdown_event.is_set():
        msg = q.safe_get(timeout=0.1)
        if msg is not None:
            yield msg


@sse_router.get("/stream")
async def stream(request: Request):
    shutdown_event = request.app.state.sse_shutdown_event

    def generator():
        # must immediately yield to return 200 OK response to client,
        # otherwise response is only sent on first event
        yield "\n"
        for message in messages(shutdown_event):
            yield str(message)

    return StreamingResponse(generator(), media_type="text/event-stream")


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
        title="Observation Execution Tool API",
        openapi_url=f"{API_PATH}/openapi.json",
        docs_url=f"{API_PATH}/ui",
    )
    app.include_router(activities_router, prefix=API_PATH)
    app.include_router(procedures_router, prefix=API_PATH)
    app.include_router(sse_router, prefix=API_PATH)

    app.exception_handler(GatewayTimeout)(timeout_handler)

    return app

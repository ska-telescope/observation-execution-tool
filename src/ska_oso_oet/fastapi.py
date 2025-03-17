import logging
import multiprocessing
from os import getenv
from threading import Event

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import StreamingResponse
from pubsub import pub

from ska_oso_oet.event import topics
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure.application import PrepareProcessCommand
from ska_oso_oet.procedure.domain import FileSystemScript, ProcedureInput
from ska_oso_oet.ui import Message
from ska_oso_oet.utils.ui import call_and_respond_fastapi

KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")
API_PREFIX = f"/{KUBE_NAMESPACE}/oet/fastapi"

router = APIRouter()
LOGGER = logging.getLogger(__name__)


@router.get("/")
async def root():
    LOGGER.debug("Got FastAPI request, sending message")
    script = FileSystemScript("file:///tmp/scripts/hello_world_without_sb.py")
    cmd = PrepareProcessCommand(script=script, init_args=ProcedureInput(subarray_id=1))
    summary = call_and_respond_fastapi(
        topics.request.procedure.create,
        topics.procedure.lifecycle.created,
        cmd=cmd,
    )

    return {"message": "Hello World!", "summary": str(summary)}


def messages(shutdown_event: Event):  # -> Generator[Message, None, None]:
    """
    A generator of Message objects created from received pubsub events
    """
    # must immediately yield to return 200 OK response to client,
    # otherwise response is only sent on first event
    yield "\n"
    mp_context = multiprocessing.get_context()
    q = MPQueue(ctx=mp_context)

    def add_to_q(topic: pub.Topic = pub.AUTO_TOPIC, **kwargs):
        kwargs["topic"] = topic.name
        other = {}
        if "request_id" in kwargs:
            other["id"] = kwargs["request_id"]
            del kwargs["request_id"]

        msg = Message(kwargs, **other)
        q.put(msg)

    pub.subscribe(add_to_q, pub.ALL_TOPICS)

    # shutdown_event = current_app.config["shutdown_event"]
    # while not shutdown_event.is_set():
    while not shutdown_event.is_set():
        msg = q.safe_get(timeout=0.1)
        if msg is not None:
            yield str(msg)


@router.get("/stream")
async def stream(request: Request):
    shutdown_event = request.app.state.sse_shutdown_event
    return StreamingResponse(messages(shutdown_event), media_type="text/event-stream")


def create_app():
    app = FastAPI(
        openapi_url=f"{API_PREFIX}/openapi.json",
        docs_url=f"{API_PREFIX}/ui",
    )
    app.include_router(router, prefix=API_PREFIX)
    # TODO need CORS middleware, amongst other things
    return app

# import logging
# import multiprocessing
from os import getenv

# from threading import Event
# from typing import Union, Optional
#
from fastapi import APIRouter

# from fastapi.responses import StreamingResponse
# from pubsub import pub
# import jsonpickle
# from ska_oso_oet.event import topics
# from ska_oso_oet.mptools import MPQueue
# from ska_oso_oet.procedure.application import PrepareProcessCommand
# from ska_oso_oet.procedure.domain import FileSystemScript, ProcedureInput

# from ska_oso_oet.utils.ui import call_and_respond_fastapi


# TODO be used in BTN-2644
KUBE_NAMESPACE = getenv("KUBE_NAMESPACE", "ska-oso-oet")
API_PREFIX = f"/{KUBE_NAMESPACE}/oet/fastapi"

sse_router = APIRouter()
# LOGGER = logging.getLogger(__name__)
#
#
# class Message:
#     """
#     Data that is published as a server-sent event.
#     """
#
#     def __init__(
#         self,
#         data: Union[str, dict],
#         id: Optional[
#             Union[float, int, str]
#         ] = None,
#         retry: Optional[int] = None,
#     ):
#         """
#         Create a server-sent event.
#
#         :param data: The event data.
#         :param type: An optional event type.
#         :param id: An optional event ID.
#         :param retry: An optional integer, to specify the reconnect time for
#             disconnected clients of this stream.
#         """
#         self.data = data
#         self.type = type
#         self.id = id
#         self.retry = retry
#
#     def __str__(self):
#         """
#         Serialize this object to a string, according to the `server-sent events
#         specification <https://www.w3.org/TR/eventsource/>`_.
#         """
#         if isinstance(self.data, dict):
#             data = jsonpickle.dumps(self.data)
#         else:
#             data = self.data
#         lines = ["data:{value}".format(value=line) for line in data.splitlines()]
#         if self.type:
#             lines.insert(0, "event:{value}".format(value=self.type))
#         if self.id:
#             lines.append("id:{value}".format(value=self.id))
#         if self.retry:
#             lines.append("retry:{value}".format(value=self.retry))
#         return "\n".join(lines) + "\n\n"
#
#     def __eq__(self, other):
#         return (
#             isinstance(other, self.__class__)
#             and self.data == other.data
#             and self.type == other.type
#             and self.id == other.id
#             and self.retry == other.retry
#         )
#
#
# def messages(shutdown_event: Event):  # -> Generator[Message, None, None]:
#     """
#     A generator of Message objects created from received pubsub events
#     """
#     # must immediately yield to return 200 OK response to client,
#     # otherwise response is only sent on first event
#     yield "\n"
#     mp_context = multiprocessing.get_context()
#     q = MPQueue(ctx=mp_context)
#
#     def add_to_q(topic: pub.Topic = pub.AUTO_TOPIC, **kwargs):
#         kwargs["topic"] = topic.name
#         other = {}
#         if "request_id" in kwargs:
#             other["id"] = kwargs["request_id"]
#             del kwargs["request_id"]
#
#         msg = Message(kwargs, **other)
#         q.put(msg)
#
#     pub.subscribe(add_to_q, pub.ALL_TOPICS)
#
#     # shutdown_event = current_app.config["shutdown_event"]
#     # while not shutdown_event.is_set():
#     while not shutdown_event.is_set():
#         msg = q.safe_get(timeout=0.1)
#         if msg is not None:
#             yield str(msg)
#
#
# @sse_router.get("/stream")
# async def stream(request: Request):
#     shutdown_event = request.app.state.sse_shutdown_event
#     return StreamingResponse(messages(shutdown_event), media_type="text/event-stream")
#

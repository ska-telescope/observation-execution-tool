"""
The ska_oso_oet.utils.ui module contains common helper code for the UI layers.
"""
import os
import time
from importlib.metadata import version
from queue import Empty, Queue
from typing import Optional

import flask
from fastapi import HTTPException
from pubsub import pub
from pydantic import BaseModel, Field

from ska_oso_oet.procedure import domain

# time allowed for Flask <-> other ProcWorker communication before timeout
TIMEOUT = 30


KUBE_NAMESPACE = os.getenv("KUBE_NAMESPACE", "ska-oso-oet")
OET_MAJOR_VERSION = version("ska-oso-oet").split(".")[0]
# The base path includes the namespace which is known at runtime
# to avoid clashes in deployments, for example in CICD
API_PATH = f"/{KUBE_NAMESPACE}/oet/api/v{OET_MAJOR_VERSION}"


class ProcedureInput(BaseModel):
    """
    Note: This is different to the lower level ProcedureInput that allows things like
        ProcedureInput(1, 'a', subarray_id=1)
        Instead this type would be like ProcedureInput(args=[1,'a'], kwargs={"subarray_id":1})
    """

    args: list = Field(default_factory=list)
    kwargs: dict = Field(default_factory=dict)


class ScriptArgs(BaseModel):
    init: Optional[ProcedureInput] = None
    main: Optional[ProcedureInput] = None


def call_and_respond(request_topic, response_topic, *args, **kwargs):
    q = Queue(1)
    my_request_id = time.time_ns()

    # msg_src MUST be part of method signature for pypubsub to function
    def callback(msg_src, request_id, result):  # pylint: disable=unused-argument
        if my_request_id == request_id:
            q.put(result)

    pub.subscribe(callback, response_topic)

    msg_src = flask.current_app.config["msg_src"]

    # With the callback now setup, publish an event to mark the user request event
    pub.sendMessage(
        request_topic, msg_src=msg_src, request_id=my_request_id, *args, **kwargs
    )

    try:
        result = q.get(timeout=TIMEOUT)

        if isinstance(result, Exception):
            if isinstance(result, OSError):
                description = {
                    "type": result.__class__.__name__,
                    "Message": f"{result.strerror}: {result.filename}",
                }
            else:
                description = {
                    "type": result.__class__.__name__,
                    "Message": str(result),
                }
            flask.abort(500, description=description)

        return result

    except Empty:
        description = {
            "Message": (
                f"Timeout waiting for msg #{my_request_id} on topic {response_topic}"
            ),
            "type": "Timeout Error",
        }
        flask.abort(504, description=description)


def call_and_respond_fastapi(request_topic, response_topic, *args, **kwargs):
    q = Queue(1)
    my_request_id = time.time_ns()

    # msg_src MUST be part of method signature for pypubsub to function
    def callback(msg_src, request_id, result):  # pylint: disable=unused-argument
        if my_request_id == request_id:
            q.put(result)

    pub.subscribe(callback, response_topic)

    msg_src = "FastAPIWorker"

    # With the callback now setup, publish an event to mark the user request event
    pub.sendMessage(
        request_topic, msg_src=msg_src, request_id=my_request_id, *args, **kwargs
    )

    try:
        result = q.get(timeout=TIMEOUT)

        if isinstance(result, Exception):
            if isinstance(result, OSError):
                detail = f"{result.strerror}: {result.filename}"
            else:
                detail = str(result)
            raise HTTPException(500, detail=detail)
        return result

    except Empty as err:
        detail = f"Timeout waiting for msg #{my_request_id} on topic {response_topic}"

        raise HTTPException(504, detail=detail) from err


def convert_request_to_procedure_input(
    api_input: ProcedureInput,
) -> domain.ProcedureInput:
    """
    :param api_input: Request with the args and kwargs, eg {'args': [1, 2], 'kwargs': {'subarray_id': 42}}
    :return: The ProcedureInput, eg <ProcedureInput(1, 2, subarray_id=42)>
    """
    return domain.ProcedureInput(*api_input.args, **api_input.kwargs)

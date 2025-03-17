"""
The ska_oso_oet.utils.ui module contains common helper code for the UI layers.
"""
import time
from queue import Empty, Queue

import flask
from pubsub import pub

from ska_oso_oet.procedure import domain

# time allowed for Flask <-> other ProcWorker communication before timeout
TIMEOUT = 30


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


def convert_request_dict_to_procedure_input(fn_dict: dict) -> domain.ProcedureInput:
    """
    Convert the dict of arguments for a single function into the domain.ProcedureInput

    :param fn_dict: Dict of the args and kwargs, eg {'args': [1, 2], 'kwargs': {'subarray_id': 42}}
    :return: The ProcedureInput, eg <ProcedureInput(1, 2, subarray_id=42)>
    """
    fn_args = fn_dict.get("args", [])
    fn_kwargs = fn_dict.get("kwargs", {})
    return domain.ProcedureInput(*fn_args, **fn_kwargs)

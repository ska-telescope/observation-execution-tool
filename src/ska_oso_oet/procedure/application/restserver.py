import json
import multiprocessing
import time
from queue import Empty, Queue
from typing import Generator, Optional, Union

import flask
import jsonpickle
from flask import Blueprint, current_app, stream_with_context
from pubsub import pub

from ska_oso_oet.event import topics
from ska_oso_oet.mptools import MPQueue
from ska_oso_oet.procedure import domain
from ska_oso_oet.procedure.application import application

# from werkzeug.serving import WSGIRequestHandler
# WSGIRequestHandler.protocol_version = "HTTP/1.1"

# Blueprints for the REST API
ProcedureAPI = Blueprint("procedures", __name__)
ActivityAPI = Blueprint("activities", __name__)

# time allowed for Flask <-> other ProcWorker communication before timeout
TIMEOUT = 10


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


def _get_summary_or_404(pid):
    """
    Get a ProcedureSummary, raising a Flask 404 if not found.

    :param pid: ID of Procedure
    :return: ProcedureSummary
    """
    summaries = call_and_respond(
        topics.request.procedure.list, topics.procedure.pool.list, pids=[pid]
    )

    if not summaries:
        description = {
            "type": "ResourceNotFound",
            "Message": f"No information available for PID={pid}",
        }

        flask.abort(404, description=description)
    else:
        return summaries[0]


@ProcedureAPI.route("/procedures", methods=["GET"])
def get_procedures():
    """
    List all Procedures.

    This returns a list of Procedure JSON representations for all
    Procedures held by the service.

    :return: list of Procedure JSON representations
    """

    summaries = call_and_respond(
        topics.request.procedure.list, topics.procedure.pool.list, pids=None
    )
    return flask.jsonify(
        {"procedures": [make_public_procedure_summary(s) for s in summaries]}
    )


@ProcedureAPI.route("/procedures/<int:procedure_id>", methods=["GET"])
def get_procedure(procedure_id: int):
    """
    Get a Procedure.

    This returns the Procedure JSON representation of the requested
    Procedure.

    :param procedure_id: ID of the Procedure to return
    :return: Procedure JSON
    """
    summary = _get_summary_or_404(procedure_id)
    return flask.jsonify({"procedure": make_public_procedure_summary(summary)})


@ProcedureAPI.route("/procedures", methods=["POST"])
def create_procedure():
    """
    Create a new Procedure.

    This method requests creation of a new Procedure as specified in the JSON
    payload POSTed to this function.

    :return: JSON summary of created Procedure
    """
    if not flask.request.json or "script" not in flask.request.json:
        description = {"type": "Malformed Request", "Message": "Script missing"}
        flask.abort(400, description=description)
    script_dict = flask.request.json["script"]

    if (
        not isinstance(script_dict, dict)
        or "script_uri" not in script_dict.keys()
        or "script_type" not in script_dict.keys()
    ):
        description = {
            "type": "Malformed Request",
            "Message": "Malformed script in request",
        }
        flask.abort(400, description=description)
    script_type = script_dict.get("script_type")
    script_uri = script_dict.get("script_uri")
    script = None

    if script_type == "filesystem":
        script = domain.FileSystemScript(script_uri)
    elif script_type == "git":
        if script_dict.get("git_args"):
            git_args = domain.GitArgs(**script_dict.get("git_args"))
        else:
            git_args = domain.GitArgs()
        script = domain.GitScript(
            script_uri,
            git_args=git_args,
            create_env=script_dict.get("create_env", False),
        )
    else:
        description = {
            "type": "Malformed Request",
            "Message": f"Script type {script_type} not supported",
        }
        flask.abort(400, description=description)

    if "script_args" in flask.request.json and not isinstance(
        flask.request.json["script_args"], dict
    ):
        description = {
            "type": "Malformed Request",
            "Message": "Malformed script_args in request",
        }
        flask.abort(400, description=description)
    script_args = flask.request.json.get("script_args", {})

    init_dict = script_args.get("init", {})
    init_args = init_dict.get("args", [])
    init_kwargs = init_dict.get("kwargs", {})

    procedure_input = domain.ProcedureInput(*init_args, **init_kwargs)
    prepare_cmd = application.PrepareProcessCommand(
        script=script, init_args=procedure_input
    )

    summary = call_and_respond(
        topics.request.procedure.create,
        topics.procedure.lifecycle.created,
        cmd=prepare_cmd,
    )

    return flask.jsonify({"procedure": make_public_procedure_summary(summary)}), 201


@ProcedureAPI.route("/procedures/<int:procedure_id>", methods=["PUT"])
def update_procedure(procedure_id: int):
    """
    Update a Procedure resource using the desired Procedure state described in
    the PUT JSON payload.

    :param procedure_id: ID of Procedure to modify
    :return: ProcedureSummary reflecting the final state of the Procedure
    """
    summary = _get_summary_or_404(procedure_id)

    if not flask.request.is_json:
        description = {
            "type": "Empty Response",
            "Message": "No JSON available in response",
        }
        flask.abort(400, description=description)

    if "script_args" in flask.request.json and not isinstance(
        flask.request.json["script_args"], dict
    ):
        description = {
            "type": "Malformed Response",
            "Message": "Malformed script_args in response",
        }
        flask.abort(400, description=description)
    script_args = flask.request.json.get("script_args", {})

    old_state = summary.state
    new_state = domain.ProcedureState[
        flask.request.json.get("state", summary.state.name)
    ]

    if new_state is domain.ProcedureState.STOPPED:
        if old_state is domain.ProcedureState.RUNNING:
            run_abort = flask.request.json.get("abort")
            cmd = application.StopProcessCommand(procedure_id, run_abort=run_abort)
            result = call_and_respond(
                topics.request.procedure.stop,
                topics.procedure.lifecycle.stopped,
                cmd=cmd,
            )
            # result is list of process summaries started in response to abort
            # If script was stopped and no post-termination abort script was run,
            # the result list will be empty.
            msg = f"Successfully stopped script with ID {procedure_id}"
            if result:
                msg += " and aborted subarray activity"
            return flask.jsonify({"abort_message": msg})

        else:
            msg = f"Cannot stop script with ID {procedure_id}: Script is not running"
            return flask.jsonify({"abort_message": msg})

    elif (
        old_state is domain.ProcedureState.READY
        and new_state is domain.ProcedureState.RUNNING
    ):
        run_dict = script_args.get("main", {})
        run_args = run_dict.get("args", [])
        run_kwargs = run_dict.get("kwargs", {})
        procedure_input = domain.ProcedureInput(*run_args, **run_kwargs)
        cmd = application.StartProcessCommand(
            procedure_id, fn_name="main", run_args=procedure_input
        )

        summary = call_and_respond(
            topics.request.procedure.start, topics.procedure.lifecycle.started, cmd=cmd
        )

    return flask.jsonify({"procedure": make_public_procedure_summary(summary)})


@ActivityAPI.route("/activities/<int:activity_id>", methods=["GET"])
def get_activity(activity_id):
    summaries = call_and_respond(
        topics.request.activity.list,
        topics.activity.pool.list,
        activity_id=[activity_id],
    )

    if not summaries:
        description = {
            "type": "ResourceNotFound",
            "Message": f"No information available for ID={activity_id}",
        }

        flask.abort(404, description=description)
    else:
        return (
            flask.jsonify({"activity": make_public_activity_summary(summaries[0])}),
            200,
        )


@ActivityAPI.route("/activities", methods=["GET"])
def get_activities():
    summaries = call_and_respond(
        topics.request.activity.list, topics.activity.pool.list
    )

    return (
        flask.jsonify(
            {"activities": [make_public_activity_summary(s) for s in summaries]}
        ),
        200,
    )


@ActivityAPI.route("/activities", methods=["POST"])
def run_activity():
    summary = call_and_respond(
        topics.request.activity.run, topics.activity.lifecycle.running, cmd=None
    )

    return flask.jsonify({"activity": make_public_activity_summary(summary)}), 200


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


def call_and_respond(request_topic, response_topic, *args, **kwargs):
    q = Queue(1)
    my_request_id = time.time()

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


def make_public_procedure_summary(procedure: application.ProcedureSummary):
    """
    Convert a ProcedureSummary into JSON ready for client consumption.

    The main use of this function is to replace the internal Procedure ID with
    the resource URI, e.g., 1 -> http://localhost:5000/api/v1.0/procedures/1

    :param procedure: Procedure to convert
    :return: safe JSON representation
    """
    script_args = {
        args.fn: {"args": args.fn_args.args, "kwargs": args.fn_args.kwargs}
        for args in procedure.script_args
    }

    script = {
        "script_type": procedure.script.get_type(),
        "script_uri": procedure.script.script_uri,
    }

    if isinstance(procedure.script, domain.GitScript):
        git_args = {
            "git_repo": procedure.script.git_args.git_repo,
            "git_branch": procedure.script.git_args.git_branch,
            "git_commit": procedure.script.git_args.git_commit,
        }
        script["git_args"] = git_args

    procedure_history = {
        "process_states": [
            (state[0].name, state[1]) for state in procedure.history.process_states
        ],
        "stacktrace": procedure.history.stacktrace,
    }

    return {
        "uri": flask.url_for(
            "procedures.get_procedure", procedure_id=procedure.id, _external=True
        ),
        "script": script,
        "script_args": script_args,
        "history": procedure_history,
        "state": procedure.state.name,
    }


def make_public_activity_summary(activity: application.ActivitySummary):
    """
    Convert an ActivitySummary into JSON ready for client consumption.

    The main use of this function is to replace the internal Activity ID with
    the resource URI, e.g., 1 -> http://localhost:5000/api/v1.0/procedures/1

    :param activity: ActivitySummary to convert
    :return: safe JSON representation
    """
    return {
        "uri": flask.url_for(
            "activities.get_activity", activity_id=activity.id, _external=True
        ),
        "activity_name": activity.activity_name,
        "sbd_id": activity.sbd_id,
        "pid": activity.pid,
        "prepare_only": activity.prepare_only,
    }


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

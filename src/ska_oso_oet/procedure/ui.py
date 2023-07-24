"""
The ska_oso_oet.procedure.ui package contains code that belong to the OET
procedure UI layer. This consists of the Procedure REST resources.
"""
import os

import flask

from ska_oso_oet.event import topics
from ska_oso_oet.procedure import application, domain
from ska_oso_oet.utils.ui import (
    call_and_respond,
    convert_request_dict_to_procedure_input,
)


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

    procedure_input = convert_request_dict_to_procedure_input(init_dict)
    prepare_cmd = application.PrepareProcessCommand(
        script=script, init_args=procedure_input
    )

    summary = call_and_respond(
        topics.request.procedure.create,
        topics.procedure.lifecycle.created,
        cmd=prepare_cmd,
    )

    return flask.jsonify({"procedure": make_public_procedure_summary(summary)}), 201


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
        procedure_input = convert_request_dict_to_procedure_input(run_dict)
        cmd = application.StartProcessCommand(
            procedure_id, fn_name="main", run_args=procedure_input
        )

        summary = call_and_respond(
            topics.request.procedure.start, topics.procedure.lifecycle.started, cmd=cmd
        )

    return flask.jsonify({"procedure": make_public_procedure_summary(summary)})


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
        "uri": f"{os.environ.get('OET_REST_URI','http://localhost/api/v1.0')}/procedures/{procedure.id}",
        "script": script,
        "script_args": script_args,
        "history": procedure_history,
        "state": procedure.state.name,
    }

"""
The ska_oso_oet.activity.ui module contains code that belongs to the activity
UI/presentation layer. This layer is the means by which external users or
systems would interact with activities.
"""
import flask

from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.event import topics
from ska_oso_oet.ui import API_PATH
from ska_oso_oet.utils.ui import (
    call_and_respond,
    convert_request_dict_to_procedure_input,
)


def get_activity(activity_id):
    summaries = call_and_respond(
        topics.request.activity.list,
        topics.activity.pool.list,
        activity_ids=[activity_id],
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


def run_activity():
    request_body = flask.request.json
    script_args = {
        fn: convert_request_dict_to_procedure_input(fn_args)
        for (fn, fn_args) in request_body.get("script_args", {}).items()
    }

    cmd = ActivityCommand(
        request_body["activity_name"],
        request_body["sbd_id"],
        request_body.get("prepare_only", False),
        request_body.get("create_env", False),
        script_args,
    )
    summary = call_and_respond(
        topics.request.activity.run, topics.activity.lifecycle.running, cmd=cmd
    )

    return flask.jsonify({"activity": make_public_activity_summary(summary)}), 201


def make_public_activity_summary(
    activity: ActivitySummary,
):
    """
    Convert an ActivitySummary into JSON ready for client consumption.

    The main use of this function is to replace the internal Activity ID with
    the resource URI, e.g., 1 -> http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1

    :param activity: ActivitySummary to convert
    :return: safe JSON representation
    """
    activity.uri = flask.url_for(
        f"{API_PATH}.ska_oso_oet_activity_ui_get_activity",
        activity_id=activity.id,
        _external=True,
    )

    return activity.model_dump(exclude={"id"}, by_alias=True)

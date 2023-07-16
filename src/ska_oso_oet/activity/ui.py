"""
The ska_oso_oet.activity.ui module contains code that belongs to the activity
UI/presentation layer. This layer is the means by which external users or
systems would interact with activities.
"""
import flask

import os
from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.event import topics
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
    # import pdb
    # pdb.set_trace()
    request_body = flask.request.json
    print(f"request_body {request_body}")
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
    print(f"cmd {cmd}")
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
    the resource URI, e.g., 1 -> http://localhost:5000/api/v1.0/procedures/1

    :param activity: ActivitySummary to convert
    :return: safe JSON representation
    """
    script_args = {
        fn: {
            "args": activity.script_args[fn].args,
            "kwargs": activity.script_args[fn].kwargs,
        }
        for fn in activity.script_args.keys()
    }
    return {
        "uri": f"{os.environ.get('OET_REST_URI', 'https://localhost/api/v1.0')}/procedures/{activity.id}",
        "activity_name": activity.activity_name,
        "sbd_id": activity.sbd_id,
        "procedure_id": activity.pid,
        "prepare_only": activity.prepare_only,
        "script_args": script_args,
        "activity_states": [
            (state_enum.name, timestamp)
            for (state_enum, timestamp) in activity.activity_states
        ],
        "state": max(
            states_to_time := dict(activity.activity_states), key=states_to_time.get
        ).name,
    }

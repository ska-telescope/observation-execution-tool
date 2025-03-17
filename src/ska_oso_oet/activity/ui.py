"""
The ska_oso_oet.activity.ui module contains code that belongs to the activity
UI/presentation layer. This layer is the means by which external users or
systems would interact with activities.
"""
from fastapi import APIRouter, HTTPException, Response

from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.event import topics
from ska_oso_oet.utils.ui import (
    call_and_respond_fastapi,
    convert_request_dict_to_procedure_input,
)

activities_router = APIRouter(prefix="/activities")


@activities_router.get("/{activity_id}")
def get_activity(activity_id):
    summaries = call_and_respond_fastapi(
        topics.request.activity.list,
        topics.activity.pool.list,
        activity_ids=[activity_id],
    )

    if not summaries:
        description = {
            "type": "ResourceNotFound",
            "Message": f"No information available for ID={activity_id}",
        }

        raise HTTPException(404, detail=description)
    else:
        return {"activity": _make_public_activity_summary(summaries[0])}


@activities_router.get("/")
def get_activities():
    summaries = call_and_respond_fastapi(
        topics.request.activity.list, topics.activity.pool.list
    )

    return {"activities": [_make_public_activity_summary(s) for s in summaries]}


@activities_router.post("/", status_code=201)
def run_activity(request_body: dict):
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
    summary = call_and_respond_fastapi(
        topics.request.activity.run, topics.activity.lifecycle.running, cmd=cmd
    )

    return {"activity": _make_public_activity_summary(summary)}


def _make_public_activity_summary(
    activity: ActivitySummary,
):
    """
    Convert an ActivitySummary into JSON ready for client consumption.

    The main use of this function is to replace the internal Activity ID with
    the resource URI, e.g., 1 -> http://localhost:5000/ska-oso-oet/oet/api/v1/procedures/1

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
        "uri": f"http://localhost:5000/ska-oso-oet/oet/api/v1/activities/{activity.id}",
        # flask.url_for(
        #     f"{API_PATH}.ska_oso_oet_activity_ui_get_activity",
        #     activity_id=activity.id,
        #     _external=True,
        # ),
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
        "sbi_id": activity.sbi_id,
    }

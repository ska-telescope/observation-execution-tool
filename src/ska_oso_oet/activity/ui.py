"""
The ska_oso_oet.activity.ui module contains code that belongs to the activity
UI/presentation layer. This layer is the means by which external users or
systems would interact with activities.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.event import topics
from ska_oso_oet.utils.ui import (
    ScriptArgs,
    call_and_respond_fastapi,
    convert_request_to_procedure_input,
)

activities_router = APIRouter(prefix="/activities", tags=["Activities"])


class ActivityPostRequest(BaseModel):
    sbd_id: str
    activity_name: str
    script_args: ScriptArgs
    prepare_only: bool = False
    create_env: bool = False


@activities_router.get(
    "/{activity_id}",
    response_model=ActivitySummary,
    description="Return the a summary of the Activity with given activity_id.",
)
def get_activity(activity_id: int) -> ActivitySummary:
    summaries = call_and_respond_fastapi(
        topics.request.activity.list,
        topics.activity.pool.list,
        activity_ids=[activity_id],
    )

    if not summaries:
        detail = {
            "type": "ResourceNotFound",
            "Message": f"No information available for ID={activity_id}",
        }

        raise HTTPException(404, detail=detail)
    else:
        return summaries[0]


@activities_router.get(
    "/",
    response_model=list[ActivitySummary],
    description="Return a list of all the Activity summaries.",
)
def get_activities() -> list[ActivitySummary]:
    summaries = call_and_respond_fastapi(
        topics.request.activity.list, topics.activity.pool.list
    )

    return summaries


@activities_router.post(
    "/",
    status_code=201,
    response_model=ActivitySummary,
    description=(
        "Loads the script from the SBDefinition for the given Activity and prepares it"
        " for execution and then executes (unless prepare_only=True)."
    ),
)
def run_activity(request_body: ActivityPostRequest) -> ActivitySummary:
    script_args = {
        fn: convert_request_to_procedure_input(fn_args)
        for (fn, fn_args) in request_body.script_args
        if fn_args is not None
    }

    cmd = ActivityCommand(
        request_body.activity_name,
        request_body.sbd_id,
        request_body.prepare_only,
        request_body.create_env,
        script_args,
    )
    summary = call_and_respond_fastapi(
        topics.request.activity.run, topics.activity.lifecycle.running, cmd=cmd
    )

    return summary

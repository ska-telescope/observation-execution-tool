"""
The ska_oso_oet.activity.ui module contains code that belongs to the activity
UI/presentation layer. This layer is the means by which external users or
systems would interact with activities.
"""
# pylint: disable=unused-argument
from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_oet.activity.application import ActivityCommand, ActivitySummary
from ska_oso_oet.auth import OPERATOR_ROLE_FOR_TELESCOPE, Permissions, Scopes
from ska_oso_oet.event import topics
from ska_oso_oet.utils.ui import (
    ProcedureInput,
    ScriptArgs,
    call_and_respond,
    convert_request_to_procedure_input,
)

activities_router = APIRouter(prefix="/activities", tags=["Activities"])


class ActivityPostRequest(BaseModel):
    sbd_id: str
    activity_name: str = Field(examples=["observe"])
    script_args: ScriptArgs = Field(
        default=ScriptArgs(init=ProcedureInput(args=[], kwargs={})),
        examples=[ScriptArgs(init=ProcedureInput(kwargs={"subarray_id": 1}))],
    )
    prepare_only: bool = False
    create_env: bool = False


@activities_router.get(
    "/{activity_id}",
    response_model=ActivitySummary,
    summary="Get the Activity with the given activity_id",
    description=(
        "Returns a summary of the Activity if it exists "
        "within the OET, with details of its state and related Procedure"
    ),
)
def get_activity(
    activity_id: int,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.ACTIVITY_READ},
        ),
    ],
) -> ActivitySummary:
    summaries = call_and_respond(
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
    summary="Get all Activities",
    description="Returns a list of all the Activity summaries.",
)
def get_activities(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.ACTIVITY_READ},
        ),
    ]
) -> list[ActivitySummary]:
    summaries = call_and_respond(
        topics.request.activity.list, topics.activity.pool.list
    )

    return summaries


@activities_router.post(
    "/",
    status_code=201,
    response_model=ActivitySummary,
    summary="Create a new Activity and start its execution",
    description=(
        "Loads the SBDefinition from the ODA and the script from Git or the filesystem"
        " for the given Activity. It is prepare forexecution as an associated Procedure"
        " and then executed (unless prepare_only=True)."
    ),
)
def run_activity(
    request_body: ActivityPostRequest,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.ACTIVITY_READ},
        ),
    ],
) -> ActivitySummary:
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
    summary = call_and_respond(
        topics.request.activity.run, topics.activity.lifecycle.running, cmd=cmd
    )

    return summary

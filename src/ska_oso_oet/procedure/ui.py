"""
The ska_oso_oet.procedure.ui package contains code that belong to the OET
procedure UI layer. This consists of the Procedure REST resources.
"""
# pylint: disable=unused-argument
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ska_aaa_authhelpers import AuthContext, Role

from ska_oso_oet.auth import OPERATOR_ROLE_FOR_TELESCOPE, Permissions, Scopes
from ska_oso_oet.event import topics
from ska_oso_oet.procedure import application, domain
from ska_oso_oet.procedure.domain import FileSystemScript
from ska_oso_oet.utils.ui import (
    ProcedureInput,
    ScriptArgs,
    call_and_respond,
    convert_request_to_procedure_input,
)

procedures_router = APIRouter(prefix="/procedures", tags=["Procedures"])

Script = Annotated[
    domain.FileSystemScript | domain.GitScript,
    Field(discriminator="script_type"),
]


class ProcedurePostRequest(BaseModel):
    script: Script = Field(
        examples=[
            FileSystemScript(script_uri="file:///tmp/scripts/hello_world_without_sb.py")
        ]
    )
    script_args: ScriptArgs = Field(
        default=ScriptArgs(init=ProcedureInput(args=[], kwargs={})),
        examples=[ScriptArgs(init=ProcedureInput(kwargs={"subarray_id": 1}))],
    )


class ProcedurePutRequest(BaseModel):
    script_args: ScriptArgs = Field(
        default=[ScriptArgs(init=ProcedureInput(args=[], kwargs={}))]
    )
    state: Optional[domain.ProcedureState] = Field(
        default=None, examples=[domain.ProcedureState.RUNNING]
    )  # Optional as no state in the request should be treated as a no-op
    abort: bool = False


@procedures_router.get(
    "/",
    response_model=list[application.ProcedureSummary],
    summary="Get all Procedures",
    description="Returns a list of all prepared and running Procedures.",
)
def get_procedures(
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.ACTIVITY_READ},
        ),
    ]
) -> list[application.ProcedureSummary]:
    summaries = call_and_respond(
        topics.request.procedure.list, topics.procedure.pool.list, pids=None
    )
    return summaries


@procedures_router.get(
    "/{procedure_id}",
    response_model=application.ProcedureSummary,
    summary="Get the Procedure with the given procedure_id",
    description=(
        "Returns a summary of the Procedure if it exists "
        "within the OET, with details of its state and arguments."
    ),
)
def get_procedure(
    procedure_id: int,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.ACTIVITY_READ},
        ),
    ],
) -> application.ProcedureSummary:
    summary = _get_summary_or_404(procedure_id)
    return summary


@procedures_router.post(
    "/",
    status_code=201,
    response_model=application.ProcedureSummary,
    summary="Create a new Procedure and prepare it for execution",
    description=(
        "Loads the requested script as a Procedure and prepares it for execution in a"
        " subprocess."
    ),
)
def create_procedure(
    request_body: ProcedurePostRequest,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.PROCEDURE_EXECUTE},
        ),
    ],
) -> application.ProcedureSummary:
    procedure_input = request_body.script_args.init
    prepare_cmd = application.PrepareProcessCommand(
        script=request_body.script,
        init_args=convert_request_to_procedure_input(procedure_input),
    )
    summary = call_and_respond(
        topics.request.procedure.create,
        topics.procedure.lifecycle.created,
        cmd=prepare_cmd,
    )

    return summary


@procedures_router.put(
    "/{procedure_id}",
    response_model=application.ProcedureSummary | application.AbortSummary,
    summary="Update the Procedure with the given procedure_id",
    description=(
        "Updates the Procedure by setting to the desiredstate in the request. "
        "This can be used to start execution by setting the Procedure state "
        "attribute to RUNNING or stop execution by setting state to STOPPED."
    ),
)
def update_procedure(
    procedure_id: int,
    request_body: ProcedurePutRequest,
    auth: Annotated[
        AuthContext,
        Permissions(
            roles={Role.SW_ENGINEER, OPERATOR_ROLE_FOR_TELESCOPE},
            scopes={Scopes.PROCEDURE_EXECUTE},
        ),
    ],
) -> application.ProcedureSummary | application.AbortSummary:
    summary = _get_summary_or_404(procedure_id)

    old_state = summary.state
    new_state = request_body.state

    if new_state is domain.ProcedureState.STOPPED:
        if old_state is domain.ProcedureState.RUNNING:
            run_abort = request_body.abort
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
            return application.AbortSummary(abort_message=msg)

        else:
            msg = f"Cannot stop script with ID {procedure_id}: Script is not running"
            return application.AbortSummary(abort_message=msg)

    elif (
        old_state is domain.ProcedureState.READY
        and new_state is domain.ProcedureState.RUNNING
    ):
        procedure_input = request_body.script_args.main
        cmd = application.StartProcessCommand(
            procedure_id,
            fn_name="main",
            run_args=convert_request_to_procedure_input(procedure_input),
        )

        summary = call_and_respond(
            topics.request.procedure.start, topics.procedure.lifecycle.started, cmd=cmd
        )

    return summary


def _get_summary_or_404(pid: int) -> application.ProcedureSummary:
    """
    Get a ProcedureSummary, raising a 404 if not found.

    :param pid: ID of Procedure
    :return: ProcedureSummary
    """
    summaries = call_and_respond(
        topics.request.procedure.list, topics.procedure.pool.list, pids=[pid]
    )

    if not summaries:
        detail = f"No information available for PID={pid}"
        raise HTTPException(404, detail=detail)
    else:
        return summaries[0]

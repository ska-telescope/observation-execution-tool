"""
The ska_oso_oet.procedure.ui package contains code that belong to the OET
procedure UI layer. This consists of the Procedure REST resources.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ska_oso_oet.event import topics
from ska_oso_oet.procedure import application, domain
from ska_oso_oet.utils.ui import (
    ScriptArgs,
    call_and_respond_fastapi,
    convert_request_to_procedure_input,
)

procedures_router = APIRouter(prefix="/procedures", tags=["Procedures"])


Script = Annotated[
    domain.FileSystemScript | domain.GitScript,
    Field(discriminator="script_type"),
]


class ProcedurePostRequest(BaseModel):
    script: Script
    script_args: ScriptArgs


class ProcedurePutRequest(BaseModel):
    script_args: Optional[ScriptArgs] = None
    state: Optional[
        domain.ProcedureState
    ] = None  # Optional as no state in the request should be treated as a no-op
    abort: bool = False


@procedures_router.get(
    "/",
    response_model=list[application.ProcedureSummary],
    description="Returns a list of all prepared and running procedures.",
)
def get_procedures() -> list[application.ProcedureSummary]:
    summaries = call_and_respond_fastapi(
        topics.request.procedure.list, topics.procedure.pool.list, pids=None
    )
    return summaries


@procedures_router.get(
    "/{procedure_id}",
    response_model=application.ProcedureSummary,
    description="Returns a summary of the Procedure with the given procedure_id.",
)
def get_procedure(procedure_id: int) -> application.ProcedureSummary:
    summary = _get_summary_or_404(procedure_id)
    return summary


@procedures_router.post(
    "/",
    status_code=201,
    response_model=application.ProcedureSummary,
    description=(
        "Loads the requested script as a Procedure and prepares it for execution."
    ),
)
def create_procedure(
    request_body: ProcedurePostRequest,
) -> application.ProcedureSummary:
    procedure_input = request_body.script_args.init
    prepare_cmd = application.PrepareProcessCommand(
        script=request_body.script,
        init_args=convert_request_to_procedure_input(procedure_input),
    )
    summary = call_and_respond_fastapi(
        topics.request.procedure.create,
        topics.procedure.lifecycle.created,
        cmd=prepare_cmd,
    )

    return summary


@procedures_router.put(
    "/{procedure_id}",
    response_model=application.ProcedureSummary | application.AbortSummary,
    description=(
        "Updates the Procedure with the given procedure_id by setting to the desired"
        " state in the request. This can be used to start execution by setting the"
        " Procedure state attribute to RUNNING or stop execution by setting state to"
        " STOPPED."
    ),
)
def update_procedure(
    procedure_id: int, request_body: ProcedurePutRequest
) -> application.ProcedureSummary | application.AbortSummary:
    summary = _get_summary_or_404(procedure_id)

    old_state = summary.state
    new_state = request_body.state

    if new_state is domain.ProcedureState.STOPPED:
        if old_state is domain.ProcedureState.RUNNING:
            run_abort = request_body.abort
            cmd = application.StopProcessCommand(procedure_id, run_abort=run_abort)
            result = call_and_respond_fastapi(
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

        summary = call_and_respond_fastapi(
            topics.request.procedure.start, topics.procedure.lifecycle.started, cmd=cmd
        )

    return summary


def _get_summary_or_404(pid: int) -> application.ProcedureSummary:
    """
    Get a ProcedureSummary, raising a 404 if not found.

    :param pid: ID of Procedure
    :return: ProcedureSummary
    """
    summaries = call_and_respond_fastapi(
        topics.request.procedure.list, topics.procedure.pool.list, pids=[pid]
    )

    if not summaries:
        detail = f"No information available for PID={pid}"
        raise HTTPException(404, detail=detail)
    else:
        return summaries[0]

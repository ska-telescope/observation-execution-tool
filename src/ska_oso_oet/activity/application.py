"""
The ska_oso_oet.activity.application module contains code related
to OET 'activities' that belong in the application layer. This application
layer holds the application interface, delegating to objects in the domain
layer for business rules and actions.
"""
import dataclasses
import itertools
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from pubsub import pub
from ska_db_oda.persistence.unitofwork.filesystemunitofwork import FilesystemUnitOfWork
from ska_db_oda.persistence.unitofwork.postgresunitofwork import PostgresUnitOfWork
from ska_oso_pdm import SBDefinition
from ska_oso_pdm._shared import TelescopeType
from ska_oso_pdm.sb_definition.procedures import (
    FilesystemScript,
    GitScript,
    PythonArguments,
    PythonProcedure,
)
from ska_oso_pdm.sb_instance import ActivityCall, FunctionArgs, SBInstance

from ska_oso_oet.activity.domain import Activity, ActivityState
from ska_oso_oet.event import topics
from ska_oso_oet.procedure import domain
from ska_oso_oet.procedure.application import (
    PrepareProcessCommand,
    ProcedureSummary,
    StartProcessCommand,
)

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class ActivityCommand:
    """ """

    activity_name: str
    sbd_id: str
    prepare_only: bool
    create_env: bool
    script_args: Dict[str, domain.ProcedureInput]


@dataclasses.dataclass
class ActivitySummary:
    id: int  # pylint: disable=invalid-name
    pid: int
    sbd_id: str
    activity_name: str
    prepare_only: bool
    script_args: Dict[str, domain.ProcedureInput]
    activity_states: List[Tuple[ActivityState, float]]
    sbi_id: str


class ActivityService:
    """
    ActivityService provides the high-level interface and facade for
    the activity domain.

    The interface is used to run activities referenced by Scheduling Blocks.
    Each activity will run a script (or `procedure`) but ActivityService
    will create the necessary commands for Procedure domain to create
    and execute the scripts.
    """

    def __init__(
        self,
    ):
        # ActivityService does not have state history updates implemented yet so we store a list of
        # states for each activity where the latest state in the list is the current state
        self.states: Dict[int, List[Tuple[ActivityState, float]]] = {}
        self.script_args: Dict[int, Dict[str, domain.ProcedureInput]] = {}
        self.activities: Dict[int, Activity] = {}
        # We need to store this state as the service needs to check if a procedure that has been created
        # is the result of an activity request
        self.request_ids_to_aid: Dict[int, int] = {}

        # counter used to generate activity ID for new activities
        self._aid_counter = itertools.count(1)

        self._oda = (
            PostgresUnitOfWork()
            if os.getenv("ODA_BACKEND_TYPE", "postgres") == "postgres"
            else FilesystemUnitOfWork()
        )

    def prepare_run_activity(self, cmd: ActivityCommand, request_id: int) -> None:
        """
        Prepare to run the activity of a Scheduling Block. This includes retrieving the script
        from the scheduling block and sending the request messages to the
        ScriptExecutionService to prepare the script.

        The request_id is required to be propagated through the messages sent to the Procedure layer,
        so the REST layer can wait for the correct response event.

        :param cmd: dataclass argument capturing the activity name and SB ID
        :param request_id: The original request_id from the REST layer
        """
        aid = next(self._aid_counter)
        with self._oda as oda:
            sbd: SBDefinition = oda.sbds.get(cmd.sbd_id)
            telescope = sbd.telescope
            sbi = self._create_sbi(telescope, cmd, sbd_version=sbd.metadata.version)
            sbi = oda.sbis.add(sbi)
            oda.commit()

        if (pdm_script := sbd.activities.get(cmd.activity_name)) is None:
            raise KeyError(
                f"Activity '{cmd.activity_name}' not present in the SBDefinition"
                f" {cmd.sbd_id}"
            )

        script = self._get_oet_script(pdm_script, cmd.create_env)
        script_args = self._combine_script_args(pdm_script, cmd)
        sbd_path = self.write_sbd_to_file(sbd)
        script_args["main"].kwargs.update({"sb_json": sbd_path, "sbi_id": sbi.sbi_id})

        prepare_cmd = PrepareProcessCommand(
            script=script,
            init_args=script_args.get("init", domain.ProcedureInput()),
        )
        pub.sendMessage(
            topics.request.procedure.create,
            # Setting the msg_src as None means the republish logic will recognise the
            # message has originated from its local pypubsub and should be republished
            msg_src=None,
            request_id=request_id,
            cmd=prepare_cmd,
        )

        # This should be the first state to be added so create a new list
        self.states[aid] = [(ActivityState.TODO, time.time())]

        # The Activity dataclass is an internal representation of the Activity. The procedure_id will be populated
        # once the procedure created event has been received
        self.activities[aid] = Activity(
            activity_id=aid,
            procedure_id=None,
            activity_name=cmd.activity_name,
            sbd_id=cmd.sbd_id,
            prepare_only=cmd.prepare_only,
            sbi_id=sbi.sbi_id,
        )
        self.script_args[aid] = script_args
        self.request_ids_to_aid[request_id] = aid

    def complete_run_activity(
        self, prepared_summary: ProcedureSummary, request_id: int
    ) -> Optional[ActivitySummary]:
        """
        Complete the request to run the Activity, using the ProcedureSummary that is now available.
        This includes updating the Activity with the procedure_id, sending the request to start the procedure if prepare_only is not set to True,
        and returning the ActivitySummary.

        :param prepared_summary: the ProcedureSummary for the Procedure related to the requested Activity
        :param request_id: The original request_id from the REST layer
        :returns: an ActivitySummary describing the state of the Activity that the Procedure is linked to,
                    or None if the Procedure was not created from an Activity
        """
        try:
            aid = self.request_ids_to_aid[request_id]
        except KeyError:
            # The request_id does not match a request sent to the activity domain, so the procedure is not linked to an activity
            return None

        activity = self.activities[aid]
        # Now the ProcedureSummary is available, update the Activity with the procedure_id
        activity.procedure_id = prepared_summary.id

        if not activity.prepare_only:
            #  TODO: should we allow here for multiple functions or limit to just main as is assumed by PM?
            fns_to_start = [fn for fn in self.script_args[aid].keys() if fn != "init"]
            for fn in fns_to_start:
                start_cmd = StartProcessCommand(
                    prepared_summary.id,
                    fn_name=fn,
                    run_args=self.script_args[aid][fn],
                    force_start=True,
                )
                pub.sendMessage(
                    topics.request.procedure.start,
                    # Setting the msg_src as None means the republish logic will recognise the
                    # message has originated from its local pypubsub and should be republished
                    msg_src=None,
                    request_id=request_id,
                    cmd=start_cmd,
                )

        return self._summarise(aid)

    def summarise(
        self, activity_ids: Optional[List[int]] = None
    ) -> List[ActivitySummary]:
        """
        Return ActivitySummary objects for Activities with the requested IDs.

        This method accepts an optional list of integers, representing the
        Activity IDs to summarise. If the IDs are left undefined,
        ActivitySummary objects for all current Activities will be returned.

        :param activity_ids: optional list of Activity IDs to summarise.
        :return: list of ActivitySummary objects
        """
        all_activity_ids = self.states.keys()
        if activity_ids is None:
            activity_ids = all_activity_ids

        missing_pids = {p for p in activity_ids if p not in all_activity_ids}
        if missing_pids:
            raise ValueError(f"Activity IDs not found: {missing_pids}")

        return [self._summarise(activity_id) for activity_id in activity_ids]

    def _summarise(self, aid: int) -> ActivitySummary:
        """
        Return a ActivitySummary for the Activity with the given ID.

        :param aid: Activity ID to summarise
        :return: ActivitySummary
        """
        state = self.states[aid]
        activity = self.activities[aid]
        script_args = self.script_args[aid]
        return ActivitySummary(
            id=aid,
            pid=activity.procedure_id,
            activity_name=activity.activity_name,
            sbd_id=activity.sbd_id,
            script_args=script_args,
            activity_states=state,
            prepare_only=activity.prepare_only,
            sbi_id=activity.sbi_id,
        )

    def _get_oet_script(
        self, pdm_script: PythonProcedure, create_env: bool
    ) -> domain.ExecutableScript:
        """
        Converts the PDM representation of the script retrieved from the SB into the OET representation.
        """
        if isinstance(pdm_script, GitScript):
            git_args = domain.GitArgs(
                git_repo=pdm_script.repo, git_branch=pdm_script.branch
            )
            return domain.GitScript(
                script_uri=pdm_script.path,
                git_args=git_args,
                create_env=create_env,
            )
        elif isinstance(pdm_script, FilesystemScript):
            return domain.FileSystemScript(script_uri=pdm_script.path)
        else:
            raise RuntimeError(
                f"Cannot run script with type {pdm_script.__class__.__name__}"
            )

    def _combine_script_args(
        self, pdm_script: PythonProcedure, cmd: ActivityCommand
    ) -> dict[str, domain.ProcedureInput]:
        """
        Combines the function args from the SB with any overwrites sent in the command,
        returning a dict of the OET representation of the args for each function.
        """

        script_args = {
            fn: domain.ProcedureInput(
                *pdm_script.function_args[fn].args,
                **pdm_script.function_args[fn].kwargs,
            )
            for fn in pdm_script.function_args
        }

        script_args.update(cmd.script_args)

        return script_args

    def write_sbd_to_file(self, sbd: SBDefinition) -> str:
        """
        Writes the SBD json to a temporary file location and returns the path.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json", encoding="utf-8"
        ) as f:
            path = f.name
            LOGGER.debug("Writing SB %s to path: %s", sbd.sbd_id, path)
            f.write(sbd.model_dump_json())

        return path

    def _create_sbi(
        self, telescope: TelescopeType, cmd: ActivityCommand, sbd_version: int
    ) -> SBInstance:
        """
        Creates an SBInstance from the relevant fields in the command.
        """
        function_args = [
            FunctionArgs(
                function_name=fn_name,
                function_args=PythonArguments(
                    args=list(procedure_input.args), kwargs=procedure_input.kwargs
                ),
            )
            for (fn_name, procedure_input) in cmd.script_args.items()
        ]

        # sbi_id is left as None and will be set when uploaded to the ODA
        return SBInstance(
            interface="https://schema.skao.int/ska-oso-pdm-sbi/0.1",
            telescope=telescope,
            sbd_ref=cmd.sbd_id,
            sbd_version=sbd_version,
            activities=[
                ActivityCall(
                    activity_ref=cmd.activity_name,
                    executed_at=datetime.now(tz=timezone.utc),
                    runtime_args=function_args,
                )
            ],
        )

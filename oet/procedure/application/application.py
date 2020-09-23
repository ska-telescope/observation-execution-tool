"""
The oet.procedure.application module holds classes and functionality that
belong in the application layer of the OET. This layer holds the application
interface, delegating to objects in the domain layer for business rules and
actions.
"""
import copy
import dataclasses
import typing

from .. import domain

ABORT_SCRIPT_URI = 'file:///app/scripts/abort.py'


@dataclasses.dataclass
class PrepareProcessCommand:
    """
    PrepareProcessCommand is input argument dataclass for the
    ScriptExecutionService prepare command. It holds all the information
    required to load and prepare a Python script ready for execution.
    """
    script_uri: str
    init_args: domain.ProcedureInput


@dataclasses.dataclass
class StartProcessCommand:
    """
    StartProcessCommand is the input argument dataclass for the
    ScriptExecutionService start command. It holds the references required to
    start a prepared script process along with any late-binding runtime
    arguments the script may require.
    """
    process_uid: int
    run_args: domain.ProcedureInput


@dataclasses.dataclass
class ProcedureSummary:
    """
    ProcedureSummary is a brief representation of a runtime Procedure. It
    captures essential information required to describe a Procedure and to
    distinguish it from other Procedures.
    """
    id: int  # pylint: disable=invalid-name
    script_uri: str
    script_args: typing.Dict[str, domain.ProcedureInput]
    created_time: str
    state: domain.ProcedureState


@dataclasses.dataclass
class StopProcessCommand:
    """
    StopProcessCommand is the input argument dataclass for the
    ScriptExecutionService Stop command. It holds the references required to
    Stop a script process along with any late-binding runtime
    arguments the script may require.
    """
    process_uid: int


class ScriptExecutionService:
    """
    ScriptExecutionService provides the high-level interface and facade for
    the script execution domain (i.e., the 'procedure' domain).

    The interface is used to load and run Python scripts in their own
    independent Python child process.
    """

    def __init__(self, abort_script_uri: str = ABORT_SCRIPT_URI):
        """
        Create a new ScriptExecutionService.

        The .stop() method of this ScriptExecutionService can run a second
        script once the current process has been terminated. By default, this
        second script calls SubArrayNode.abort() to halt further activities
        on the sub-array controlled by the terminated script. To run a
        different script, define the script URI in the abort_script_uri
        argument to this constructor.

        :param abort_script_uri: URI of post-termination script
        """
        self._process_host = domain.ProcessManager()
        self._abort_script_uri = abort_script_uri

    def _create_summary(self, pid: int) -> ProcedureSummary:
        """
        Return a ProcedureSummary for the Procedure with the given ID.

        :param pid: Procedure ID to summarise
        :return: ProcedureSummary
        """
        procedure = self._process_host.procedures[pid]
        summary = ProcedureSummary(
            id=pid,
            script_uri=procedure.script_uri,
            script_args=copy.deepcopy(procedure.script_args),
            created_time=procedure.created_time,
            state=procedure.state
        )
        return summary

    def prepare(self, cmd: PrepareProcessCommand) -> ProcedureSummary:
        """
        Load and prepare a Python script for execution, but do not commence
        execution.

        :param cmd: dataclass argument capturing the script identity and load
            arguments
        :return:
        """
        pid = self._process_host.create(cmd.script_uri, init_args=cmd.init_args)
        summary = self._create_summary(pid)
        return summary

    def start(self, cmd: StartProcessCommand) -> ProcedureSummary:
        """
        Start execution of a prepared procedure.

        :param cmd: dataclass argument capturing the execution arguments
        :return:
        """
        self._process_host.run(cmd.process_uid, run_args=cmd.run_args)
        return self._create_summary(cmd.process_uid)

    def summarise(self, pids: typing.Optional[typing.List[int]] = None) \
            -> typing.List[ProcedureSummary]:
        """
        Return ProcedureSummary objects for Procedures with the requested IDs.

        This method accepts an optional list of integers, representing the
        Procedure IDs to summarise. If the pids is left undefined,
        ProcedureSummary objects for all current Procedures will be returned.

        :param pids: optional list of Procedure IDs to summarise.
        :return: list of ProcedureSummary objects
        """
        all_pids = self._process_host.procedures.keys()
        if not pids:
            pids = all_pids

        missing_pids = {p for p in pids if p not in all_pids}
        if missing_pids:
            raise ValueError(f'Process IDs not found: {missing_pids}')

        return [self._create_summary(pid) for pid in pids]

    def stop(self,
             cmd: StopProcessCommand,
             run_abort=True) -> typing.List[ProcedureSummary]:
        """
        Stop execution of a running procedure, optionally running a
        second script once the first process has terminated.

        :param cmd: dataclass argument capturing the execution arguments
        :param run_abort: runs post-termination abort script when True
        :return:
        """
        subarray_id = self._get_subarray_id(cmd.process_uid)
        self._process_host.stop(cmd.process_uid)

        # exit early if not instructed to run post-termination script
        if not run_abort:
            # Did not start a new process so return empty list
            return []

        # prepare second script
        prepare_cmd = PrepareProcessCommand(
            script_uri=self._abort_script_uri,
            init_args=domain.ProcedureInput(subarray_id=subarray_id)
        )
        procedure_summary = self.prepare(prepare_cmd)

        # start the second script
        run_cmd = StartProcessCommand(
            process_uid=procedure_summary.id,
            run_args=domain.ProcedureInput()
        )
        summary = self.start(run_cmd)
        return [summary]

    def _get_subarray_id(self, pid: int):
        """
        Return a Subarray id for given procedure ID.

        :param pid: Procedure ID to summarise
        :return: subarray id
        """
        procedure_summary = self.summarise(pids=[pid])[0]
        init_dict = procedure_summary.script_args['init']
        init_kwargs = init_dict.kwargs
        if 'subarray_id' not in init_kwargs:
            raise ValueError(f'Subarray Id not found')
        return init_kwargs['subarray_id']

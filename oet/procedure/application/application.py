"""
The oet.procedure.application module holds classes and functionality that
belong in the application layer of the OET.
"""
import copy
import dataclasses
import typing

from oet.procedure import domain


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
    id: int
    script_uri: str
    script_args: typing.Dict[str, domain.ProcedureInput]
    state: domain.ProcedureState


class ScriptExecutionService:
    """
    ScriptExecutionService provides the high-level interface and facade for
    the script execution domain (i.e., the 'procedure' domain).

    The interface is used to load and run Python scripts in their own
    independent Python child process.
    """

    def __init__(self):
        self._process_host = domain.ProcessManager()

    def _create_summary(self, pid: int):
        procedure = self._process_host.procedures[pid]
        summary = ProcedureSummary(
            id=pid,
            script_uri=procedure.script_uri,
            script_args=copy.deepcopy(procedure.script_args),
            state=procedure.state
        )
        return summary

    def prepare(self, cmd: PrepareProcessCommand) -> ProcedureSummary:
        """
        Load and prepare a Python script for execution, but do not commence execution.

        :param cmd: dataclass argument capturing the script identity and load arguments
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

    def summarise(self, pids: typing.Optional[typing.List[int]] = None) -> typing.List[ProcedureSummary]:
        all_pids = self._process_host.procedures.keys()
        if not pids:
            pids = all_pids

        missing_pids = {p for p in pids if p not in all_pids}
        if missing_pids:
            raise ValueError(f'Process IDs not found: {missing_pids}')

        return [self._create_summary(pid) for pid in pids]

"""
The oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
import dataclasses
import typing
import enum


class ProcedureState(enum.Enum):
    READY = enum.auto()
    RUNNING = enum.auto()


@dataclasses.dataclass
class ProcedureInput:
    """
    ProcedureInput is a non-functional dataclass holding the arguments passed
    to a script method.
    """

    def __init__(self, *args, **kwargs):
        self.args: tuple = args
        self.kwargs: dict = kwargs


class Procedure:
    """
    A Procedure is the OET representation of a Python script, its arguments,
    and its execution state.
    """

    def __init__(self, script_uri: str, *args, **kwargs):
        init_args = ProcedureInput(*args, **kwargs)

        self.id = None
        self.script_uri: str = script_uri
        self.script_args: typing.Dict[str, ProcedureInput] = {'init': init_args, 'run': ProcedureInput()}
        self.state = ProcedureState.READY

    def run(self, *args, **kwargs):
        if self.state is not ProcedureState.READY:
            raise Exception(f'Invalidate procedure state for run: {self.state}')

        self.state = ProcedureState.RUNNING
        self.script_args['run'] = ProcedureInput(*args, **kwargs)


class ProcessManager:
    """
    Rules:
     - 0..* prepared processes per manager
     - 0..1 running processes per manager
    """

    def __init__(self):
        self.procedures: typing.Dict[int, Procedure] = {}
        self.running: typing.Optional[Procedure] = None

        self._procedure_factory = ProcedureFactory()

    def create(self, script_uri: str, init_args: ProcedureInput) -> int:
        procedure = self._procedure_factory.create(script_uri, *init_args.args, **init_args.kwargs)

        if not self.procedures:
            pid = 1
        else:
            pid = max(self.procedures.keys()) + 1

        self.procedures[pid] = procedure
        return pid

    def run(self, process_id: int, run_args: ProcedureInput):
        if self.running:
            running_pid = self.running.id
            raise ValueError(f'Cannot start PID {process_id}: procedure {running_pid} is running')

        try:
            procedure = self.procedures[process_id]
        except KeyError as e:
            raise ValueError(f'Process {process_id} not found') from e

        procedure.run(*run_args.args, **run_args.kwargs)


class ProcedureFactory:
    """
    A factory class for creating no-op Procedure objects.
    """

    def create(self, script_uri: str, *args, **kwargs) -> Procedure:
        """
        Create a new Procedure. Right now this just creates the Procedure
        object. In a functional implementation this would create an OS
        (sub)process.

        :param script_uri: URI of Python script to load
        :param args: positional arguments to give to the script process constructor
        :param kwargs: keyword/value arguments to pass to the script process constructor

        :return: Script process object.
        """
        return Procedure(script_uri, *args, **kwargs)

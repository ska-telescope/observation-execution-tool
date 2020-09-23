"""
The oet.procedure.domain module holds domain entities from the script
execution domain. Entities in this domain are things like scripts,
OS processes, process supervisors, signal handlers, etc.
"""
import dataclasses
import importlib.machinery
import multiprocessing
import typing
from multiprocessing.dummy import Pool
from typing import Optional

import enum
import types
from datetime import datetime
from oet.command import SCAN_ID_GENERATOR


class ProcedureState(enum.Enum):
    """
    Represents the script execution state.

    Limited to either READY or RUNNING for this PI.
    """
    READY = enum.auto()
    RUNNING = enum.auto()
    STOP = enum.auto()


@dataclasses.dataclass
class ProcedureInput:
    """
    ProcedureInput is a non-functional dataclass holding the arguments passed
    to a script method.
    """

    def __init__(self, *args, **kwargs):
        self.args: tuple = args
        self.kwargs: dict = kwargs

    def __eq__(self, other):
        if not isinstance(other, ProcedureInput):
            return False
        if self.args == other.args and self.kwargs == other.kwargs:
            return True
        return False

    def __repr__(self):
        args = ', '.join((str(a) for a in self.args))
        kwargs = ', '.join(['{!s}={!r}'.format(k, v) for k, v in self.kwargs.items()])
        return '<ProcedureInput({})>'.format(', '.join((args, kwargs)))


class Procedure(multiprocessing.Process):
    """
    A Procedure is the OET representation of a Python script, its arguments,
    and its execution state.
    """

    def __init__(self, script_uri: str, *args,
                 scan_counter: Optional[multiprocessing.Value] = None, **kwargs):
        multiprocessing.Process.__init__(self)
        init_args = ProcedureInput(*args, **kwargs)

        self.id = None  # pylint:disable=invalid-name

        self.user_module = ModuleFactory.get_module(script_uri)
        if hasattr(self.user_module, 'init'):
            self.user_module.init(*args, **kwargs)

        self.script_uri = script_uri
        self.script_args: typing.Dict[str, ProcedureInput] = dict(init=init_args,
                                                                  run=ProcedureInput())
        self.state = ProcedureState.READY
        self.created_time = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        self._scan_counter = scan_counter

    def run(self):
        """
        Run user module script. Called from start() and executed in a child process

        This calls the main() method of the target script.
        """
        # set shared scan ID backing store, if provided
        if self._scan_counter:
            SCAN_ID_GENERATOR.backing = self._scan_counter

        args = self.script_args['run'].args
        kwargs = self.script_args['run'].kwargs
        self.user_module.main(*args, **kwargs)

    def start(self):
        """
        Start Procedure execution.

        This calls the run() method in a new child process. Set Procedure state here
        to record state within the parent process. Procedure state is then inherited by
        the child process.
        """
        if self.state is not ProcedureState.READY:
            raise Exception(f'Invalidate procedure state for run: {self.state}')

        self.state = ProcedureState.RUNNING
        super().start()


class ProcessManager:
    """
    Rules:
     - 0..* prepared processes per manager
     - 0..1 running processes per manager
    """

    def __init__(self):
        self.procedures: typing.Dict[int, Procedure] = {}
        self.running: typing.Optional[Procedure] = None
        self.procedure_complete = multiprocessing.Condition()

        self._procedure_factory = ProcedureFactory()
        self._pool = Pool()
        self._scan_id = multiprocessing.Value('i', 1)

    def create(self, script_uri: str, *, init_args: ProcedureInput) -> int:
        """
        Create a new Procedure that will, when executed, run the target Python
        script.

        :param script_uri: script URI, e.g. 'file://myscript.py'
        :param init_args: script initialisation arguments
        :return:
        """
        if not self.procedures:
            pid = 1
        else:
            pid = max(self.procedures.keys()) + 1

        procedure = self._procedure_factory.create(script_uri, *init_args.args,
                                                   scan_counter=self._scan_id, **init_args.kwargs)
        procedure.id = pid

        self.procedures[pid] = procedure

        return pid

    def run(self, process_id: int, *, run_args: ProcedureInput):
        """
        Run a prepared Procedure.

        This starts execution of the script prepared by a previous create()
        call.

        :param process_id: ID of Procedure to execute
        :param run_args: late-binding arguments to provide to the script
        :return:
        """
        if self.running:
            running_pid = self.running.id
            raise ValueError(f'Cannot start PID {process_id}: procedure {running_pid} is running')

        try:
            procedure = self.procedures[process_id]
        except KeyError as exc:
            raise ValueError(f'Process {process_id} not found') from exc

        self.running = procedure
        procedure.script_args['run'] = run_args
        procedure.start()

        def callback(*_):
            self.running = None
            del self.procedures[process_id]
            with self.procedure_complete:
                self.procedure_complete.notify_all()

        self._pool.apply_async(_wait_for_process, (procedure,), {}, callback, callback)

    def stop(self, process_id):
        """
        stop a running Procedure.

        This stops execution of a currently running script.

        :param process_id: ID of Procedure to stop
        :return:
        """
        if self.running is None:
            raise ValueError(f'Cannot stop PID {process_id}: procedure is not running')

        try:
            procedure = self.procedures[process_id]
        except KeyError as exc:
            raise ValueError(f'Process {process_id} not found') from exc

        if procedure.is_alive():
            procedure.terminate()
            # join any potentially zombie process, allowing it to clean up
            multiprocessing.active_children()
            # set running to None here instead of waiting for run() callback
            # so that abort script can be started while callback does clean-up
            self.running = None


def _wait_for_process(process, **_):
    """
    Block until the given process completes.
    :param process: process to wait for
    :param _: unused kwargs
    """
    process.join()


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


class ModuleFactory:
    """
    Factory class used to return Python Module instances from a variety of
    storage back-ends.
    """

    @staticmethod
    def get_module(script_uri):
        """
        Load Python code from storage, returning an executable Python module.

        :param script_uri: URI of script to load
        :return: Python module
        """
        if script_uri.startswith('test://'):
            loader = ModuleFactory._null_module_loader
        elif script_uri.startswith('file://'):
            loader = ModuleFactory._load_module_from_file
        else:
            raise ValueError('Script URI type not handled: {}'.format(script_uri))

        return loader(script_uri)

    @staticmethod
    def _load_module_from_file(script_uri: str) -> types.ModuleType:
        """
        Load Python module from file storage. This module handles file:///
        URIs.

        :param script_uri: URI of script to load.
        :return: Python module
        """
        # remove 'file://' prefix
        path = script_uri[7:]
        loader = importlib.machinery.SourceFileLoader('user_module', path)
        user_module = types.ModuleType(loader.name)
        loader.exec_module(user_module)
        return user_module

    @staticmethod
    def _null_module_loader(_: str) -> types.ModuleType:
        """
        Create and return an empty Python module. Handles test:/// URIs.

        :param _: URI. Will be ignored.
        :return:
        """
        def init(*_, **__):
            pass

        def main(*_, **__):
            pass

        user_module = types.ModuleType('user_module')
        user_module.main = main
        user_module.init = init

        return user_module

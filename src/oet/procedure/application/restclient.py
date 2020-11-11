"""
Client for the OET REST Service.

This client can be used to interact with a remote OET script executor. It can
be used to request 'procedure creation', which loads a Python script and
prepares it for execution; to 'start a procedure', which starts execution of a
script prepared in a prior 'create procedure' call, and to list all prepared
and running procedures held in the remote server.
"""
import dataclasses
import datetime
import logging
import operator
import os
import json
from http import HTTPStatus
from typing import Dict, List, Optional

import fire
import requests
import tabulate

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class ProcedureSummary:
    """
    Struct to hold Procedure metadata. No business logic is held in this
    class.
    """

    id: int
    uri: str
    script_uri: str
    script_args: dict
    history: dict
    state: str

    @staticmethod
    def from_json(json: dict):
        """
        Convert a Procedure JSON payload to a ProcedureSummary object

        :param json: payload to convert
        :return: equivalent ProcedureSummary instance
        """
        uid = json['uri'].split('/')[-1]
        return ProcedureSummary(
            id=uid,
            uri=json['uri'],
            script_uri=json['script_uri'],
            script_args=json['script_args'],
            history=json['history'],
            state=json['state']
        )


class RestClientUI:
    """
    OET script execution client.

    This client can be used to connect to a remote OET script execution
    service. With this client, you can create procedures, list procedures, and
    start a procedure that is ready for execution.

    Multiple procedures may be initialised, but only one script may be
    running at any one time.
    """

    def __init__(self, server_url=None):
        """
        Create a new client for the OET script execution service.

        By default, the client will attempt to connect to a server at
        localhost.

        :param server_url: URI of the target REST server
        """
        if server_url is None:
            server_url = os.getenv('OET_REST_URI',
                                   'http://oet-rest-test:5000/api/v1.0/procedures')
        self._client = RestAdapter(server_url)

    @staticmethod
    def _format_error(error_json: str) -> str:
        try:
            error_d = json.loads(error_json)
            type = error_d['type']
            message = error_d['Message']
            error = error_d['error']
            msg = f'Server encountered error {error}:\n  {type}: {message}'
        except ValueError as exc:
            # ValueError raised if error is not valid JSON. This happens at least when
            # REST server is not running and returns Connection refused error
            msg = f'The server encountered a problem: {error_json}'
        return f'{msg}'

    @staticmethod
    def _tabulate(procedures: List[ProcedureSummary]) -> str:
        table_rows = [(p.id, p.script_uri,
                       datetime.datetime.fromtimestamp(p.history['process_states']
                                                       ['CREATED'], tz=datetime.timezone.utc
                                                       ).strftime('%Y-%m-%d ' '%H:%M:%S'),
                       p.state) for p in procedures]

        headers = ['ID', 'Script', 'Creation Time', 'State']
        return tabulate.tabulate(table_rows, headers)

    @staticmethod
    def _tabulate_for_describe(procedure: List[ProcedureSummary]) -> str:

        table_row_title = [(procedure[0].id, procedure[0].script_uri, procedure[0].uri)]
        headers_title = ['ID', 'Script', 'URI']

        table_rows_args = [(s, procedure[0].script_args[s]['args'],
                           procedure[0].script_args[s]['kwargs'])
                           for s in procedure[0].script_args]

        headers_args = ['Method', 'Arguments', 'Keyword Arguments']

        table_rows_states = [(datetime.datetime.fromtimestamp(procedure[0].
                                                              history['process_states'][s],
                                                              tz=datetime.timezone.utc).
                                                              strftime('%Y-%m-%d %H:%M:%S.%f'), s)
                             for s in procedure[0].history['process_states']]

        table_rows_states.sort(key=operator.itemgetter(0))
        headers_states = ['Time', 'State']

        # define default table sections...
        table_sections = [
            tabulate.tabulate(table_row_title, headers_title),
            tabulate.tabulate(table_rows_states, headers_states),
            tabulate.tabulate(table_rows_args, headers_args)
        ]

        # .. and add stacktrace if present
        stacktrace = procedure[0].history['stacktrace']
        if stacktrace:
            table_sections.append(f'Stack Trace:\n------------\n{stacktrace}')

        return '\n\n'.join(table_sections)

    def list(self, pid=None) -> str:
        """
        List procedures registered on the targeted server.

        This command has an optional arguments: a numeric procedure ID to list.
        If no ID is specified, all procedures will be listed.

        :param pid: (optional) IDs of procedure to list
        :return: Table entries for requested procedure(s)
        """
        try:
            procedures = self._client.list(pid)
            return self._tabulate(procedures)
        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            return self._format_error(str(err))

    def create(self, script_uri: str, *args, subarray_id=1, **kwargs) -> str:
        """
        Create a new Procedure.

        Arguments will be passed to the Procedure initialiser.

        Example:

            oet create file:///path/to/script.py 'hello' --verbose=true

        :param script_uri: script URI, e.g., file:///test.py
        :param args: script positional arguments
        :param subarray_id: Sub-array controlled by this OET instance
        :param kwargs: script keyword arguments
        :return: Table entry for created procedure.
        """
        kwargs['subarray_id'] = subarray_id
        init_args = dict(args=args, kwargs=kwargs)
        try:
            procedure = self._client.create(script_uri, init_args=init_args)
            return self._tabulate([procedure])
        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            return self._format_error(str(err))

    def start(self, *args, pid=None, **kwargs) -> str:
        """
        Start a specified Procedure.

        This will start the procedure with the specified ID. If no procedure
        ID is declared, the most recent procedure to be created will be
        started.

        Arguments provided to start will be passed to the script.

        Example:

            oet start --pid=3 'hello' --verbose=true

        :param pid: ID of the procedure to start
        :param args: late-binding position arguments for script
        :param kwargs: late-binding kwargs for script
        :return: Table entry for running procedure
        """
        if pid is None:
            procedures = self._client.list()
            if not procedures:
                return 'No procedures to start'
            procedure = procedures[-1]
            if procedure.state != "CREATED":
                return f'The last procedure created is in {procedures[-1].state} state ' \
                       'and cannot be started, please specify a valid procedure ID.'
            pid = procedure.id

        run_args = dict(args=args, kwargs=kwargs)
        try:
            procedure = self._client.start(pid, run_args=run_args)
            return self._tabulate([procedure])
        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            return self._format_error(str(err))

    def stop(self, pid=None, run_abort=True) -> str:
        """
        Stop a specified Procedure.

        This will stop the execution of a currently running procedure
        with the specified ID.If no procedure ID is declared, the first
        procedure with running status will be stopped.

        :param pid: ID of the procedure to stop
        :param run_abort: If True (default), executes abort script once running
            script has terminated
        :return: Empty table entry
        """
        if pid is None:
            running_procedures = [p for p in self._client.list() if p.state == 'RUNNING']
            if not running_procedures:
                return 'No procedures to stop'
            if len(running_procedures) > 1:
                return 'WARNING: More than one procedure is running. ' \
                       'Specify ID of the procedure to stop.'
            pid = running_procedures[0].id
        try:
            response = self._client.stop(pid, run_abort)
            return response
        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            return self._format_error(str(err))

    def describe(self, pid=None) -> str:
        """
        Display information on the specified procedure.

        This will display the state history of a specified procedure,
        including the stack trace is the procedure failed. If no procedure ID
        is declared, the last procedure to be created with be described.

        :param pid: ID of procedure to describe
        """
        if pid is None:
            procedures = self._client.list()
            if not procedures:
                return 'No procedures to describe'
            pid = procedures[-1].id
        procedure = self._client.list(pid)
        return self._tabulate_for_describe(procedure)


class RestAdapter:
    """A simple CLI REST client using python-fire for the option parsing"""

    def __init__(self, server_url):
        """
        Create a new OET REST adapter.

        :param server_url: URI of target REST server
        """
        self.server_url = server_url

    def list(self, pid: Optional[int] = None) -> List[ProcedureSummary]:
        """
        List procedures known to the OET.

        This command accepts an optional numeric procedure ID. If no ID is
        specified, all procedures will be listed.

        :param pid: (optional) ID of procedure to list
        :return: List of ProcedureSummary instances
        """
        if pid is not None:
            url = f'{self.server_url}/{pid}'
            response = requests.get(url)
            if response.status_code == HTTPStatus.OK:
                procedure_json = response.json()['procedure']
                return [ProcedureSummary.from_json(procedure_json)]
            else:
                raise Exception(response.text)

        url = self.server_url
        response = requests.get(url)
        procedures_json = response.json()['procedures']
        return [ProcedureSummary.from_json(d) for d in procedures_json]

    def create(self, script_uri: str, init_args: Dict = None) -> ProcedureSummary:
        """
        Create a new Procedure.

        Arguments given in init_args will be passed to the Procedure
        initialiser. The init_args argument should be a dict with 'args' and
        'kwargs' entries for positional and named arguments respectively,
        e.g.,

            init_args={args=[1,2,3], kwargs=dict(kw1=2, kw3='abc')}

        :param script_uri: script URI, e.g., file://test.py
        :param init_args: script initialisation arguments
        :return: Summary of created procedure.
        """
        if init_args is None:
            init_args = dict(args=[], kwargs={})

        request_json = {
            'script_uri': script_uri,
            'script_args': {
                'init': init_args,
            }
        }
        LOGGER.debug('Create payload: %s', request_json)

        response = requests.post(self.server_url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.CREATED:
            return ProcedureSummary.from_json(response_as_dict['procedure'])
        raise Exception(response.text)

    def start(self, pid, run_args=None) -> ProcedureSummary:
        """
        Start the specified Procedure.

        Arguments given in run_args will be passed to the Procedure
        entry method. The run_args argument should be a dict with 'args' and
        'kwargs' entries for positional and named arguments respectively,
        e.g.,

            run_args={args=[1,2,3], kwargs=dict(kw1=2, kw3='abc')}

        :param pid: ID of script to execute
        :param run_args: late-binding script arguments
        :return: Summary of running procedure.
        """
        url = f'{self.server_url}/{pid}'

        if run_args is None:
            run_args = dict(args=[], kwargs={})

        request_json = {
            'script_args': {
                'run': run_args
            },
            'state': 'RUNNING'
        }
        LOGGER.debug('Start payload: %s', request_json)

        response = requests.put(url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.OK:
            return ProcedureSummary.from_json(response_as_dict['procedure'])
        raise Exception(response.text)

    def stop(self, pid, run_abort=True):
        """
        Stop the specified Procedure.

        :param pid: ID of script to stop
        :param run_abort: If True (default), executes abort script once running
            script has terminated
        :return: success/failure message
        """
        url = f'{self.server_url}/{pid}'

        request_json = {
            'abort': run_abort,
            'state': 'STOPPED'
        }
        LOGGER.debug('Stop payload: %s', request_json)

        response = requests.put(url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.OK:
            return response_as_dict['abort_message']
        raise Exception(response.text)


def main():
    """
    Fire entry function to provide a CLI interface for REST client.
    """
    fire.Fire(RestClientUI)


# This statement is included so that we can run this module and test the REST
# client directly without installing the OET project
if __name__ == '__main__':
    main()

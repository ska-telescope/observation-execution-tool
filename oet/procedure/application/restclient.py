import dataclasses
import logging
from typing import List, Optional, Dict

import fire
import requests
import tabulate

LOG = logging.getLogger(__name__)


@dataclasses.dataclass
class ProcedureSummary:
    id: int
    uri: str
    script_uri: str
    script_args: dict
    state: str

    @staticmethod
    def from_json(d: dict):
        uid = d['uri'].split('/')[-1]
        return ProcedureSummary(
            id=uid,
            uri=d['uri'],
            script_uri=d['script_uri'],
            script_args=d['script_args'],
            state=d['state']
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

    def __init__(self, server_url="http://localhost:5000/api/v1.0/procedures"):
        """
        Create a new client for the OET script execution service.

        By default, the client will attempt to connect to a server at
        localhost.

        :param server_url: URI of the target REST server
        """
        self._client = RestAdapter(server_url)

    def _tabulate(self, procedures: List[ProcedureSummary]) -> str:
        table_rows = [(p.id, p.uri, p.script_uri, p.state) for p in procedures]
        headers = ['ID', 'URI', 'Script', 'State']
        return tabulate.tabulate(table_rows, headers)

    def list(self, number=None) -> str:
        """
        List procedures registered on the targeted server.

        This command has an optional arguments: a numeric procedure ID to list.
        If no ID is specified, all procedures will be listed.

        :param number: (optional) IDs of procedure to list
        :return: Table entries for requested procedure(s)
        """
        procedures = self._client.list(number)
        return self._tabulate(procedures)

    def create(self, script_uri: str, *args, **kwargs) -> str:
        """
        Create a new Procedure.

        Arguments will be passed to the Procedure initialiser.

        Example:

            oet create file://path/to/script.py 'hello' --verbose=true

        :param script_uri: script URI, e.g., file://test.py
        :param args: script positional arguments
        :param kwargs: script keyword arguments
        :return: Table entry for created procedure.
        """
        init_args = dict(args=args, kwargs=kwargs)
        procedure = self._client.create(script_uri, init_args=init_args)
        return self._tabulate([procedure])

    def start(self, number=None, *args, **kwargs) -> str:
        """
        Start a specified Procedure.

        This will start the procedure with the specified ID. If no procedure
        ID is declared, the most recent procedure to be created will be
        started.

        Arguments provided to start will be passed to the script.

        Example:

            oet start 3 'hello' --verbose=true

        :param number: ID of the procedure to start
        :param args: late-binding position arguments for script
        :param kwargs: late-binding kwargs for script
        :return: Table entry for running procedure
        """
        if number is None:
            procedures = self._client.list()
            if not procedures:
                return 'No procedures to start'
            number = procedures[-1].id

        run_args = dict(args=args, kwargs=kwargs)
        procedure = self._client.start(number, run_args=run_args)
        return self._tabulate([procedure])


class RestAdapter(object):
    """A simple CLI REST client using python-fire for the option parsing"""

    def __init__(self, server_url):
        """
        Create a new OET REST adapter.

        :param server_url: URI of target REST server
        """
        self.server_url = server_url

    def list(self, number: Optional[int] = None) -> List[ProcedureSummary]:
        """
        List procedures known to the OET.

        This command accepts an optional numeric procedure ID. If no ID is
        specified, all procedures will be listed.

        :param number: (optional) ID of procedure to list
        :return: List of ProcedureSummary instances
        """
        if number is not None:
            url = f'{self.server_url}/{number}'
            response = requests.get(url)
            procedure_json = response.json()['procedure']
            return [ProcedureSummary.from_json(procedure_json)]
        else:
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
        LOG.debug('Create payload: {}'.format(request_json))

        response = requests.post(self.server_url, json=request_json)
        procedure_json = response.json()['procedure']

        return ProcedureSummary.from_json(procedure_json)

    def start(self, number, run_args=None) -> ProcedureSummary:
        """
        Start the specified Procedure.

        Arguments given in run_args will be passed to the Procedure
        entry method. The run_args argument should be a dict with 'args' and
        'kwargs' entries for positional and named arguments respectively,
        e.g.,

            run_args={args=[1,2,3], kwargs=dict(kw1=2, kw3='abc')}

        :param number: ID of script to execute
        :param run_args: late-binding script arguments
        :return: Summary of running procedure.
        """
        url = f'{self.server_url}/{number}'

        if run_args is None:
            run_args = dict(args=[], kwargs={})

        request_json = {
            'script_args': {
                'run': run_args
            },
            'state': 'RUNNING'
        }
        LOG.debug('Start payload: {}'.format(request_json))

        response = requests.put(url, json=request_json)
        response_json = response.json()
        if response.status_code == 200:
            return ProcedureSummary.from_json(response_json['procedure'])
        else:
            raise Exception(response_json['error'])


def main():
    fire.Fire(RestClientUI)


if __name__ == '__main__':
    adapter = RestAdapter(server_url='http://localhost:5000/api/v1.0/procedures')
    result = adapter.list(3)
    print(result)
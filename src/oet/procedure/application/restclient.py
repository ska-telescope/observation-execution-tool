"""
Client for the OET REST Service.

This client can be used to interact with a remote OET script executor. It can
be used to request 'procedure creation', which loads a Python script and
prepares it for execution; to 'start a procedure', which starts execution of a
script prepared in a prior 'create procedure' call, and to list all prepared
and running procedures held in the remote server.
"""
import dataclasses
from http import HTTPStatus

import datetime
import fire
import json
import logging
import operator
import os
import requests
import sseclient
import tabulate
from typing import Dict, List, Optional, Generator

LOGGER = logging.getLogger(__name__)


#
# Monkey patch SSEclient to solve issue with gzip-compressed SSE streams
#
# Patch taken verbatim from:
# https://github.com/Count-Count/sseclient/tree/dont_use_raw_reads_with_gzipped_or_chunked_streams
#
def iter_content(self):
    if hasattr(self.resp.raw, '_fp') and \
            hasattr(self.resp.raw._fp, 'fp') and \
            hasattr(self.resp.raw._fp.fp, 'read1') and \
            not self.resp.raw.chunked and \
            not self.resp.raw.getheader("Content-Encoding"):

        def generate():
            while True:
                chunk = self.resp.raw._fp.fp.read1(self.chunk_size)
                if not chunk:
                    break
                yield chunk

        return generate()

    else:
        # short reads cannot be used, this will block until
        # the full chunk size is actually read
        return self.resp.iter_content(self.chunk_size)

sseclient.SSEClient.iter_content = iter_content


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

    TOPIC_DICT = {
        'request.procedure.create': lambda
            evt: f'User request: prepare {evt["cmd"]["script_uri"]} for execution on subarray {evt["cmd"]["init_args"]["kwargs"]["subarray_id"]}',
        'request.procedure.list': lambda
            evt: f'User request to list all the procedures is received',
        'request.procedure.start': lambda
            evt: f'User request: start execution of process #{evt["cmd"]["process_uid"]}',
        'request.procedure.stop': lambda
            evt: f'User request: stop procedure #{evt["cmd"]["process_uid"]} with {"" if evt["cmd"]["run_abort"] else "no"} abort',
        'procedure.pool.list': lambda
            evt: f'Enumerating current procedures and status',
        'procedure.lifecycle.created': lambda
            evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script_uri"]}) ready for execution on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}',
        'procedure.lifecycle.started': lambda
            evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script_uri"]}) started execution on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}',
        'procedure.lifecycle.stopped': lambda
            evt: RestClientUI._extract_result_from_abort_result(evt),
        'procedure.lifecycle.failed': lambda
            evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script_uri"]}) execution failed on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}',
        'user.script.announce': lambda
            evt: f'Script message: {evt["msg"]}',
        'sb.lifecycle.allocated': lambda
            evt: f'Resources allocated using SB {evt["sb_id"]}',
        'sb.lifecycle.observation.started': lambda
            evt: f'Observation for SB {evt["sb_id"]} started',
        'sb.lifecycle.observation.finished.succeeded': lambda
            evt: f'Observation for SB {evt["sb_id"]} complete',
        'sb.lifecycle.observation.finished.failed': lambda
            evt: f'Observation for SB {evt["sb_id"]} failed',
        'subarray.resources.allocated': lambda
            evt: f'Subarray {evt["subarray_id"]}: resources allocated',
        'subarray.resources.deallocated': lambda
            evt: f'Subarray {evt["subarray_id"]}: resources released',
        'subarray.configured': lambda
            evt: f'Subarray {evt["subarray_id"]} configured',
        'subarray.scan.started': lambda
            evt: f'Subarray {evt["subarray_id"]}: scan started',
        'subarray.scan.finished': lambda
            evt: f'Subarray {evt["subarray_id"]}: scan complete',
        'subarray.fault': lambda
            evt: f'Subarray {evt["subarray_id"]} error: {evt["error"]}',
        'scan.lifecycle.configure.started': lambda
            evt: f'SB {evt["sb_id"]}: configuring for scan {evt["scan_id"]}',
        'scan.lifecycle.configure.complete': lambda
            evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} configuration complete',
        'scan.lifecycle.configure.failed': lambda
            evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} configuration failed',
        'scan.lifecycle.start': lambda
            evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} starting',
        'scan.lifecycle.end.succeeded': lambda
            evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} complete',
        'scan.lifecycle.end.failed': lambda
            evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} failed',
    }

    @staticmethod
    def _extract_result_from_abort_result(evt: dict):
        """
        PI8 workaround.

        A script stopping naturally returns a single ProcedureSummary.
        However, an aborted script returns a _list_ of ProcedureSummaries, one
        summary for each post-abort script. If the result is a list, this
        method returns the first result found, which is enough for PI8.

        TODO refactor stop message to a common type
        """
        try:
            result = evt['result'][0]
        except IndexError:
            # stop script but no post-abort script run
            # no other info available in message!
            return f'Procedure stopped'
        except (TypeError, KeyError):
            result = evt['result']
        return f'Procedure {result["id"]} ({result["script_uri"]}) execution complete {result["script_args"]["init"]["kwargs"]["subarray_id"]}'

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
            if 'Filename' in error_d:
                msg = f"{error_d['Message']}: {error_d['Filename']}"
            else:
                msg = f"{error_d['Error']}: {error_d['Message']}"
        except ValueError:
            # ValueError raised if error is not valid JSON. This happens at least when
            # REST server is not running and returns Connection refused error
            msg = error_json
            raise
        return f'The server encountered a problem: {msg}'

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

    def start(self, *args, pid=None, listen=True, **kwargs) -> Generator[str, None, None]:
        """
        Start a specified Procedure.

        This will start the procedure with the specified ID. If no procedure
        ID is declared, the most recent procedure to be created will be
        started.

        Arguments provided to start will be passed to the script.

        Example:

            oet start --pid=3 'hello' --verbose=true

        :param pid: ID of the procedure to start
        :param listen: True to display events
        :param args: late-binding position arguments for script
        :param kwargs: late-binding kwargs for script
        :return: Table entry for running procedure
        """
        if pid is None:
            procedures = self._client.list()
            if not procedures:
                yield 'No procedures to start'
                return

            procedure = procedures[-1]
            if procedure.state != "CREATED":
                yield f'The last procedure created is in {procedures[-1].state} state ' \
                       'and cannot be started, please specify a valid procedure ID.'
                return
            pid = procedure.id

        run_args = dict(args=args, kwargs=kwargs)
        try:
            if listen:
                listener = self.listen()

            procedure = self._client.start(pid, run_args=run_args)
            for line in self._tabulate([procedure]).splitlines(keepends=False):
                yield line

            if listen:
                yield ''
                yield 'Events'
                yield '------'
                yield ''

                for msg in listener:
                    yield msg

        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            yield self._format_error(str(err))

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

    def listen(self, topics: Optional[str] = 'all', exclude: Optional[str] = 'request,procedure.pool'):
        """
        Display real time oet events published by scripts.

        :param topics: event topics to display, or 'all' for all (default='all')
        :param exclude: event topics to exclude (default='request,procedure.pool')
        """
        if topics == 'all':
            topics = list(RestClientUI.TOPIC_DICT.keys())
        else:
            topics = topics.split(',')

        exclude_topics = exclude.split(',')
        to_exclude = [t for e in exclude_topics for t in topics if e and t.startswith(e)]
        topics = [t for t in topics if t not in to_exclude]

        try:
            for evt in self._client.listen():
                output = self._filter_event_messages(evt, topics)
                if output:
                    yield f'- {output}'
        except KeyboardInterrupt as err:
            LOGGER.debug(f'received exception {err}')
        except Exception as err:
            LOGGER.debug(f'received exception {err}')
            return self._format_error(str(err))

    @staticmethod
    def _filter_event_messages(evt: sseclient.Event, topics: List[str]) -> str:
        if not evt.data:
            return ''

        try:
            event_dict = json.loads(evt.data)
        except json.decoder.JSONDecodeError as e:
            return f'ERROR Could not parse event: {evt}'

        event_topic = event_dict.get('topic', None)
        if event_topic not in topics:
            return ''

        # no topic defined - print anyway
        formatter = RestClientUI.TOPIC_DICT.get(event_topic, str)
        try:
            return formatter(event_dict)
        except KeyError:
            LOGGER.debug('Error parsing event: %s', event_dict)
            return ''


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
                raise Exception(response.json()['error'].split(': ', 1)[1])

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
        response_json = response.json()
        if response.status_code == HTTPStatus.CREATED:
            return ProcedureSummary.from_json(response_json['procedure'])
        raise Exception(response_json['error'].split(': ', 1)[1])

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
        response_json = response.json()
        if response.status_code == HTTPStatus.OK:
            return ProcedureSummary.from_json(response_json['procedure'])
        raise Exception(response_json['error'].split(': ', 1)[1])

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
        response_json = response.json()
        if response.status_code == HTTPStatus.OK:
            return response_json['abort_message']
        raise Exception(response_json['error'].split(': ', 1)[1])

    def listen(self) -> Generator[sseclient.Event, None, None]:
        """
        Listen real time Oet events

        :return: event messages
        """
        url = self.server_url.replace('procedures', 'stream')

        for msg in sseclient.SSEClient(url):
            LOGGER.debug('Event: %s', msg)
            yield msg


def main():
    """
    Fire entry function to provide a CLI interface for REST client.
    """
    fire.Fire(RestClientUI)


# This statement is included so that we can run this module and test the REST
# client directly without installing the OET project
if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    main()

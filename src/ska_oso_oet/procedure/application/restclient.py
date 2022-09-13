# Relax pylint. We deliberately catch all exceptions in the CLI in order to
# return a user-friendly message.
#
# pylint: disable=broad-except
"""
Command-line client for the OET REST Service.

This program is used to control and monitor a remote OET script executor. It can
be used to request 'procedure creation', which loads a Python script and
prepares it for execution; to 'start a procedure', which starts execution of a
script prepared in a prior 'create procedure' call, and to list all prepared
and running procedures held in the remote server.
"""
import dataclasses
import datetime
import itertools as IT
import json
import logging
import operator
import os
from http import HTTPStatus
from typing import Dict, Generator, List, Optional

import fire
import requests
import sseclient
import tabulate

LOGGER = logging.getLogger(__name__)


#
# Monkey patch SSEclient to solve issue with gzip-compressed SSE streams
#
# Patch taken verbatim from:
# https://github.com/Count-Count/sseclient/tree/dont_use_raw_reads_with_gzipped_or_chunked_streams
#
def iter_content(self):
    if (
        hasattr(self.resp.raw, "_fp")
        and hasattr(self.resp.raw._fp, "fp")  # pylint: disable=protected-access
        and hasattr(self.resp.raw._fp.fp, "read1")  # pylint: disable=protected-access
        and not self.resp.raw.chunked
        and not self.resp.raw.getheader("Content-Encoding")
    ):

        def generate():
            while True:
                chunk = self.resp.raw._fp.fp.read1(  # pylint: disable=protected-access
                    self.chunk_size
                )
                if not chunk:
                    break
                yield chunk

        return generate()

    else:
        # short reads cannot be used, this will block until
        # the full chunk size is actually read
        return self.resp.iter_content(self.chunk_size)


sseclient.SSEClient.iter_content = iter_content


#
# Monkey patch the Fire flag handling: Fire uses flags for arguments which should be
# passed to the underlying function, and 'Fire flags' that are used by Fire internally (eg --help) which
# are expected after `--` in the CLI call.
# For functions without kwargs this doesn't seem to cause an issue, but if kwargs are present in the function
# signature then --help is converted to a boolean and passed to the function.
# For example, `oet start --help` would pass `help=True` to the function, but `oet start -- --help`
# would show the docstring help.
# The latter is not intuitive for the user, so this monkey patch will always treat --help as a Fire flag
#
# Taken from issue:
# https://github.com/google/python-fire/issues/258
def _SeparateFlagArgs(args):
    # Original functionality in case user does pass `--`
    if "--" in args:
        separator_index = len(args) - 1 - args[::-1].index("--")  # index of last --
        flag_args = args[separator_index + 1 :]
        args = args[:separator_index]
        return args, flag_args

    # If not, treat --help as special case
    try:
        index = args.index("--help")
        args = args[:index]
        return args, ["--help"]
    except ValueError:
        return args, []


fire.core.parser.SeparateFlagArgs = _SeparateFlagArgs


@dataclasses.dataclass
class ProcedureSummary:
    """
    Struct to hold Procedure metadata. No business logic is held in this
    class.
    """

    id: int
    uri: str
    script_args: dict
    script: dict
    history: dict
    state: str

    @staticmethod
    def from_json(procedure_json: dict):
        """
        Convert a Procedure JSON payload to a ProcedureSummary object

        :param procedure_json: payload to convert
        :return: equivalent ProcedureSummary instance
        """
        uid = procedure_json["uri"].split("/")[-1]
        return ProcedureSummary(
            id=uid,
            uri=procedure_json["uri"],
            script_args=procedure_json["script_args"],
            script=procedure_json["script"],
            history=procedure_json["history"],
            state=procedure_json["state"],
        )


class RestClientUI:
    """
    OET command-line interface.

    This program is used to control and monitor a remote OET script executor.
    Using this tool, you can instruct the remote OET backend to load a Python
    script, call a function of that script, and abort script execution. This
    tool can also report a recent history of script execution and monitor the
    events published by the OET backend and running scripts.

    Note that multiple scripts may be loaded and prepared for execution, but
    only one script can run at a time.
    """

    TOPIC_DICT = {
        "request.procedure.create": (
            lambda evt: f'User request: prepare {evt["cmd"]["script"]["script_uri"]} for execution on subarray {evt["cmd"]["init_args"]["kwargs"]["subarray_id"]}'
        ),
        "request.procedure.list": (
            lambda evt: "User request to list all the procedures is received"
        ),
        "request.procedure.start": (
            lambda evt: f'User request: start execution of process #{evt["cmd"]["process_uid"]}'
        ),
        "request.procedure.stop": (
            lambda evt: f'User request: stop procedure #{evt["cmd"]["process_uid"]} with {"" if evt["cmd"]["run_abort"] else "no"} abort'
        ),
        "procedure.pool.list": (
            lambda evt: "Enumerating current procedures and status"
        ),
        "procedure.lifecycle.created": (
            lambda evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script"]["script_uri"]}) ready for execution on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}'
        ),
        "procedure.lifecycle.started": (
            lambda evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script"]["script_uri"]}) started execution on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}'
        ),
        "procedure.lifecycle.stopped": (
            # pylint: disable=unnecessary-lambda
            lambda evt: RestClientUI._extract_result_from_abort_result(evt)
        ),
        "procedure.lifecycle.failed": (
            lambda evt: f'Procedure {evt["result"]["id"]} ({evt["result"]["script"]["script_uri"]}) execution failed on subarray {evt["result"]["script_args"]["init"]["kwargs"]["subarray_id"]}'
        ),
        "user.script.announce": lambda evt: f'Script message: {evt["msg"]}',
        "sb.lifecycle.allocated": (
            lambda evt: f'Resources allocated using SB {evt["sb_id"]}'
        ),
        "sb.lifecycle.observation.started": (
            lambda evt: f'Observation for SB {evt["sb_id"]} started'
        ),
        "sb.lifecycle.observation.finished.succeeded": (
            lambda evt: f'Observation for SB {evt["sb_id"]} complete'
        ),
        "sb.lifecycle.observation.finished.failed": (
            lambda evt: f'Observation for SB {evt["sb_id"]} failed'
        ),
        "subarray.resources.allocated": (
            lambda evt: f'Subarray {evt["subarray_id"]}: resources allocated'
        ),
        "subarray.resources.deallocated": (
            lambda evt: f'Subarray {evt["subarray_id"]}: resources released'
        ),
        "subarray.configured": (
            lambda evt: f'Subarray {evt["subarray_id"]} configured'
        ),
        "subarray.scan.started": (
            lambda evt: f'Subarray {evt["subarray_id"]}: scan started'
        ),
        "subarray.scan.finished": (
            lambda evt: f'Subarray {evt["subarray_id"]}: scan complete'
        ),
        "subarray.fault": (
            lambda evt: f'Subarray {evt["subarray_id"]} error: {evt["error"]}'
        ),
        "scan.lifecycle.configure.started": (
            lambda evt: f'SB {evt["sb_id"]}: configuring for scan {evt["scan_id"]}'
        ),
        "scan.lifecycle.configure.complete": (
            lambda evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} configuration complete'
        ),
        "scan.lifecycle.configure.failed": (
            lambda evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} configuration failed'
        ),
        "scan.lifecycle.start": (
            lambda evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} starting'
        ),
        "scan.lifecycle.end.succeeded": (
            lambda evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} complete'
        ),
        "scan.lifecycle.end.failed": (
            lambda evt: f'SB {evt["sb_id"]}: scan {evt["scan_id"]} failed'
        ),
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
            result = evt["result"][0]
        except IndexError:
            # stop script but no post-abort script run
            # no other info available in message!
            return "Procedure stopped"
        except (TypeError, KeyError):
            result = evt["result"]
        return (
            f'Procedure {result["id"]} ({result["script"]["script_uri"]}) execution'
            f' complete {result["script_args"]["init"]["kwargs"]["subarray_id"]}'
        )

    def __init__(self, server_url=None):
        """
        Create a new client for the OET script execution service.

        By default, the client will attempt to connect to a server at
        localhost.

        :param server_url: URI of the target REST server
        """
        if server_url is None:
            server_url = os.getenv(
                "OET_REST_URI", "http://ska-oso-oet-rest-test:5000/api/v1.0/procedures"
            )
        self._client = RestAdapter(server_url)

    @staticmethod
    def _format_error(error_json: str) -> str:
        try:
            error_d = json.loads(error_json)
            msg_type = error_d["type"]
            message = error_d["Message"]
            error = error_d["error"]
            msg = f"Server encountered error {error}:\n  {msg_type}: {message}"
        except ValueError:
            # ValueError raised if error is not valid JSON. This happens at least when
            # REST server is not running and returns Connection refused error
            msg = f"The server encountered a problem: {error_json}"
        return f"{msg}"

    @staticmethod
    def _tabulate(procedures: List[ProcedureSummary]) -> str:
        table_rows = [
            (
                p.id,
                p.script["script_uri"],
                datetime.datetime.fromtimestamp(
                    p.history["process_states"][0][1], tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S"),
                p.state,
            )
            for p in procedures
        ]

        headers = ["ID", "Script", "Creation Time", "State"]
        table_sections = tabulate.tabulate(table_rows, headers)
        if procedures:
            table_sections = (
                table_sections
                + "\n For more details, use oet command:- oet describe --pid=<id>"
            )
        return table_sections

    @staticmethod
    def _tabulate_for_describe(procedure: List[ProcedureSummary]) -> str:
        table_row_title = [
            (procedure[0].id, procedure[0].script["script_uri"], procedure[0].uri)
        ]
        headers_title = ["ID", "Script", "URI"]

        table_rows_args = [
            (
                index,
                s,
                procedure[0].script_args[s]["args"],
                procedure[0].script_args[s]["kwargs"],
            )
            for index, s in enumerate(procedure[0].script_args, start=1)
        ]

        headers_args = ["Index", "Method", "Arguments", "Keyword Arguments"]
        counter = IT.count(1)
        table_rows_states = [
            (
                datetime.datetime.fromtimestamp(
                    s[1], tz=datetime.timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S.%f"),
                f"{s[0]} {next(counter)}" if s[0] == "RUNNING" else s[0],
            )
            for s in procedure[0].history["process_states"]
        ]

        table_rows_states.sort(key=operator.itemgetter(0))
        headers_states = ["Time", "State"]

        # define default table sections...
        table_sections = [
            tabulate.tabulate(table_row_title, headers_title),
            tabulate.tabulate(table_rows_states, headers_states),
            tabulate.tabulate(table_rows_args, headers_args),
        ]

        if "git_args" in procedure[0].script:
            table_row_git = [
                (
                    procedure[0].script["git_args"]["git_repo"],
                    procedure[0].script["git_args"]["git_branch"],
                    procedure[0].script["git_args"]["git_commit"],
                )
            ]

            table_row_git.sort(key=operator.itemgetter(0))
            headers_git = ["Repository", "Branch", "Commit"]
            table_sections.append(tabulate.tabulate(table_row_git, headers_git))

        # .. and add stacktrace if present
        stacktrace = procedure[0].history["stacktrace"]
        if stacktrace:
            table_sections.append(f"Stack Trace:\n------------\n{stacktrace}")

        return "\n\n".join(table_sections)

    def list(self, pid=None) -> str:
        """
        List the state of current and recently run scripts.

        This command has an optional arguments: a numeric procedure ID to list.
        If no ID is specified, all procedures will be listed.

        :param pid: (optional) IDs of procedure to list
        :return: Table entries for requested procedure(s)
        """
        try:
            procedures = self._client.list(pid)
        except Exception as err:
            LOGGER.warning("received exception %s", err)
            return self._format_error(str(err))
        return self._tabulate(procedures)

    def create(
        self,
        script_uri: str,
        *args,
        subarray_id=1,
        git_repo: str = None,
        git_branch: str = None,
        git_commit: str = None,
        create_env: bool = False,
        **kwargs,
    ) -> str:
        """
        Prepare a Procedure (=prepare to run a script).

        This command tells the OET backend to prepare to run a user script.
        The OET backend will load the requested script, prepare the Python
        environment if requested, and call the script's init function if
        present.

        The OET can load scripts from the container filesystem and from remote
        git repositories.

        The user script URI should begin with either file:// to reference a
        script that exists within the OET backend's filesystem / default
        environment, or git:// to give the relative path of a script within
        a git project.

        The OET has some default behaviour regarding non-default scripts
        such as git scripts that can be modified through use of the --git_repo,
        --git_branch, --git_commit, and --create_env command line arguments.

        1. --git_repo: By default, the OET assumes the referenced script
           belongs to the ska-oso-scripting gitlab project, and will retrieve
           the project and attempt to find the file accordingly. To point to
           a different git repository, define the --git_repo argument.

        2. --git_branch: By default, the OET retrieves the default git project
           for the specified git project (usually main or master). Defining
           the --git_branch argument will cause the specified git branch to be
           retrieved.

        3. --git-commit: By default, the OET will use the latest commit for
           the target git branch. A different commit can be specified by
           setting the  --git_commit argument to a git commit hash. Note that
           this will override any --git_branch setting.

        4. --create_env: By default, the script will execute using the
           default Python environment of the OET backend container. If the
           script has dependencies not met by the default environment, setting
           --create_env=True will instruct the OET to create a new Python
           environment and install the project's dependencies, as specified
           by the project's Poetry configuration or requirements.txt. If a
           suitable environment already exists on the backend, as denoted by
           matching git commit hash for the create request, the existing
           environment will be reused.

        Arguments will be passed to the Procedure's init function. Git
        arguments should only be provided if script_uri prefix is git://

        Example for running procedure from filesystem:

            oet create file:///scripts/observe.py subarray_id=2 --verbose=true

        Example for running procedure from git:

            oet create git://relative/path/to/script.py --git_repo=http://gitlab.com/repo-name --create_env=False

        :param script_uri: script URI, e.g., file:///test.py
        :param args: script positional arguments
        :param subarray_id: Sub-array controlled by this OET instance
        :param git_repo: Path to git repository
            (default=http://gitlab.com/ska-telescope/oso/ska-oso-scripting)
        :param git_branch: Branch within the git repository, defaults to master if not provided
        :param git_commit: Git commit hash, defaults to latest commit on the given branch.
            Branch does not need to be specified if commit hash is provided
        :param create_env: Install dependencies from the procedure source project. Set to False by default.
        :param kwargs: script keyword arguments
        :return: Table entry for created procedure.
        """

        # Iterating over the Python kwargs dictionary
        git_args = dict()
        init_kwargs = dict()
        init_kwargs["subarray_id"] = subarray_id

        for arg in kwargs.keys():
            init_kwargs[arg] = kwargs[arg]

        if git_repo:
            git_args["git_repo"] = git_repo
        if git_branch:
            git_args["git_branch"] = git_branch
        if git_commit:
            git_args["git_commit"] = git_commit

        init_args = dict(args=args, kwargs=init_kwargs)
        try:
            procedure = self._client.create(
                script_uri,
                init_args=init_args,
                git_args=git_args,
                create_env=create_env,
            )
        except Exception as err:
            LOGGER.debug("received exception %s", err)
            return self._format_error(str(err))
        return self._tabulate([procedure])

    def start(
        self, *args, pid=None, listen=True, **kwargs
    ) -> Generator[str, None, None]:
        """
        Run a Procedure.

        This will start the procedure with the specified ID. If no procedure
        ID is declared, the most recent procedure to be created will be
        started.

        By default, this interface will run the requested command and then
        immediately start listening to the OET backend's event stream so that
        events and messages emitted by the backend and user script are seen.
        To stop listening to events, press CTRL+C. Add the --listen=False
        argument to the command to run the command silent, with no connection
        to the event stream.

        This command instructs the OET to run the main() function of the
        target script. Arguments provided on the command line will be passed
        as positional and keyword arguments to the main() function.

        Examples:

            # calls main() of the last created script, passing the SBI ID to
            # the function. Equivalent to main('sbi-mvp01-20200325-00001')
            oet start sbi-mvp01-20200325-00001

            # calls main() of the script PID #3, passing the positional argument
            # and keyword arguments to the script. Equivalent to calling
            # main('hello', foo='bar')
            oet start --pid=3 'hello' --foo=bar

        :param pid: ID of the procedure to start
        :param listen: display events (default=True)
        :param args: late-binding position arguments for script
        :param kwargs: late-binding kwargs for script
        :return: Table entry for running procedure
        """
        if pid is None:
            procedures = self._client.list()
            if not procedures:
                yield "No procedures to start"
                return

            procedure = procedures[-1]
            if procedure.state != "READY":
                yield (
                    f"The last procedure created is in {procedures[-1].state} state "
                    "and cannot be started, please specify a valid procedure ID."
                )
                return
            pid = procedure.id
        else:
            procedure = self._client.list(pid)[0]
            if procedure.state != "READY":
                yield (f"Cannot start a procedure in state {procedure.state}.")
                return

        run_args = dict(args=args, kwargs=kwargs)
        try:
            if listen:
                listener = self.listen()

            procedure = self._client.start(pid, run_args=run_args)
            for line in self._tabulate([procedure]).splitlines(keepends=False):
                yield line

            if listen:
                yield ""
                yield "Events"
                yield "------"
                yield ""

                for msg in listener:
                    yield msg

        except Exception as err:
            LOGGER.debug("received exception %s", err)
            yield self._format_error(str(err))

    def stop(self, pid=None, run_abort=True) -> str:
        """
        Terminate execution.

        This will stop the execution of a currently running procedure
        with the specified ID.If no procedure ID is declared, the first
        procedure with running status will be stopped.

        :param pid: ID of the procedure to stop
        :param run_abort: If True (default), executes abort script once running
            script has terminated
        :return: Empty table entry
        """
        if pid is None:
            running_procedures = [
                p for p in self._client.list() if p.state == "RUNNING"
            ]
            if not running_procedures:
                return "No procedures to stop"
            if len(running_procedures) > 1:
                return (
                    "WARNING: More than one procedure is running. "
                    "Specify ID of the procedure to stop."
                )
            pid = running_procedures[0].id
        try:
            response = self._client.stop(pid, run_abort)
            return response
        except Exception as err:
            LOGGER.debug("received exception %s", err)
            return self._format_error(str(err))

    def describe(self, pid=None) -> str:
        """
        Display Procedure information.

        This will display the state history of a specified procedure,
        including the stack trace is the procedure failed. If no procedure ID
        is declared, the last procedure to be created with be described.

        :param pid: ID of procedure to describe
        """
        if pid is None:
            procedures = self._client.list()
            if not procedures:
                return "No procedures to describe"
            pid = procedures[-1].id
        try:
            procedure = self._client.list(pid)
        except Exception as err:
            LOGGER.debug("received exception %s", err)
            return self._format_error(str(err))
        return self._tabulate_for_describe(procedure)

    def listen(
        self,
        topics: Optional[str] = "all",
        exclude: Optional[str] = "request,procedure.pool",
    ) -> Generator[str, None, None]:
        """
        Display OET events.

        This command will display all events emitted by the OET and user scripts
        that meet the topic filter criteria set by the --topics and --exclude
        command line arguments.

        The stop displaying events, press CTRL+C.

        :param topics: event topics to display, or 'all' for all (default='all')
        :param exclude: event topics to exclude (default='request,procedure.pool')
        """
        if topics == "all":
            topics = list(RestClientUI.TOPIC_DICT.keys())
        else:
            topics = topics.split(",")

        exclude_topics = exclude.split(",")
        to_exclude = [
            t for e in exclude_topics for t in topics if e and t.startswith(e)
        ]
        topics = [t for t in topics if t not in to_exclude]

        try:
            for evt in self._client.listen():
                output = self._filter_event_messages(evt, topics)
                if output:
                    yield f"- {output}"
        except KeyboardInterrupt as err:
            LOGGER.debug("received exception %s", err)
        except Exception as err:
            LOGGER.debug("received exception %s", err)
            yield self._format_error(str(err))

    @staticmethod
    def _filter_event_messages(evt: sseclient.Event, topics: List[str]) -> str:
        if not evt.data:
            return ""

        try:
            event_dict = json.loads(evt.data)
        except json.decoder.JSONDecodeError:
            return f"ERROR Could not parse event: {evt}"

        event_topic = event_dict.get("topic", None)
        if event_topic not in topics:
            return ""

        # no topic defined - print anyway
        formatter = RestClientUI.TOPIC_DICT.get(event_topic, str)
        try:
            return formatter(event_dict)
        except KeyError:
            LOGGER.debug("Error parsing event: %s", event_dict)
            return ""


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
            url = f"{self.server_url}/{pid}"
            response = requests.get(url)
            if response.status_code == HTTPStatus.OK:
                procedure_json = response.json()["procedure"]
                return [ProcedureSummary.from_json(procedure_json)]
            else:
                raise Exception(response.text)

        url = self.server_url
        response = requests.get(url)
        procedures_json = response.json()["procedures"]
        return [ProcedureSummary.from_json(d) for d in procedures_json]

    def create(
        self,
        script_uri: str,
        init_args: Dict = None,
        git_args: Dict = None,
        create_env: bool = False,
    ) -> ProcedureSummary:
        """
        Create a new Procedure.

        Arguments given in init_args will be passed to the Procedure's
        init function. The init_args argument should be a dict with 'args' and
        'kwargs' entries for positional and named arguments respectively,
        e.g.,

            init_args={args=[1,2,3], kwargs=dict(kw1=2, kw3='abc')}

        Argument given in git_args should be a dict e.g.,
             git_args={"git_repo": "git://foo.git","git_branch": "main","git_commit": "HEAD"}

        :param script_uri: script URI, e.g., file://test.py or git://test.git
        :param init_args: script initialisation arguments
        :param git_args: git script arguments
        :param create_env: Install dependencies from the procedure source project. Set to False by default.
        :return: Summary of created procedure.
        """
        if not (script_uri.startswith("file://") or script_uri.startswith("git://")):
            raise Exception(f"Script URI type not handled: {script_uri.split('//')[0]}")

        script = dict(script_type="filesystem", script_uri=script_uri)
        if init_args is None:
            init_args = dict(args=[], kwargs={})

        if git_args and "file://" in script_uri:
            raise Exception(
                f"Invalid request, Git arguments: {git_args} are not required for"
                " Filesystem script."
            )
        if "git://" in script_uri:
            script = dict(
                script_type="git",
                script_uri=script_uri,
                git_args=git_args,
                create_env=create_env,
            )

        request_json = {
            "script_args": {
                "init": init_args,
            },
            "script": script,
        }
        LOGGER.debug("Create payload: %s", request_json)

        response = requests.post(self.server_url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.CREATED:
            return ProcedureSummary.from_json(response_as_dict["procedure"])
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
        url = f"{self.server_url}/{pid}"

        if run_args is None:
            run_args = dict(args=[], kwargs={})

        request_json = {"script_args": {"main": run_args}, "state": "RUNNING"}
        LOGGER.debug("Start payload: %s", request_json)

        response = requests.put(url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.OK:
            return ProcedureSummary.from_json(response_as_dict["procedure"])
        raise Exception(response.text)

    def stop(self, pid, run_abort=True):
        """
        Stop the specified Procedure.

        :param pid: ID of script to stop
        :param run_abort: If True (default), executes abort script once running
            script has terminated
        :return: success/failure message
        """
        url = f"{self.server_url}/{pid}"

        request_json = {"abort": run_abort, "state": "STOPPED"}
        LOGGER.debug("Stop payload: %s", request_json)

        response = requests.put(url, json=request_json)
        response_as_dict = response.json()
        if response.status_code == HTTPStatus.OK:
            return response_as_dict["abort_message"]
        raise Exception(response.text)

    def listen(self) -> Generator[sseclient.Event, None, None]:
        """
        Listen real time Oet events

        :return: event messages
        """
        url = self.server_url.replace("procedures", "stream")

        for msg in sseclient.SSEClient(url):
            LOGGER.debug("Event: %s", msg)
            yield msg


def main():
    """
    Fire entry function to provide a CLI interface for REST client.
    """
    fire.Fire(RestClientUI)


# This statement is included so that we can run this module and test the REST
# client directly without installing the OET project
if __name__ == "__main__":
    # logging.basicConfig(level=logging.DEBUG)
    main()

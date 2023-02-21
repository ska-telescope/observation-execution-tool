# pylint: disable=W0212,W0613
# - W0212(protected-access) - tests need to access protected props
# - W0613(unused-argument) - these are fixtures, not function args
"""
Unit tests for the procedure REST API module.
"""
import copy
import threading
import time
import types
from http import HTTPStatus
from typing import List
from unittest import mock

import flask
import pytest
from pubsub import pub

from ska_oso_oet import mptools
from ska_oso_oet.event import topics
from ska_oso_oet.procedure.application import restserver
from ska_oso_oet.procedure.application.application import (
    ActivityCommand,
    ActivityState,
    ActivitySummary,
    ArgCapture,
    PrepareProcessCommand,
    ProcedureHistory,
    ProcedureSummary,
    StartProcessCommand,
    StopProcessCommand,
)
from ska_oso_oet.procedure.domain import (
    FileSystemScript,
    GitArgs,
    GitScript,
    ProcedureInput,
    ProcedureState,
)

# Endpoint for the REST API
PROCEDURES_ENDPOINT = "api/v1.0/procedures"
ACTIVITIES_ENDPOINT = "api/v1.0/activities"

# Valid JSON struct for creating a new procedure
CREATE_JSON = dict(
    script={"script_type": "filesystem", "script_uri": "file:///test.py"},
    script_args={"init": dict(args=(1, 2, 3), kwargs=dict(kw1="a", kw2="b"))},
)

# object expected to be returned when creating the Procedure defined above
CREATE_SUMMARY = ProcedureSummary(
    id=1,
    script=FileSystemScript("file:///test.py"),
    script_args=[
        ArgCapture(fn="init", fn_args=ProcedureInput(1, 2, 3, kw1="a", kw2="b"), time=1)
    ],
    history=ProcedureHistory(
        process_states=[
            (ProcedureState.CREATING, 1.0),  # process starting
            (ProcedureState.IDLE, 2.0),  # process created
            (ProcedureState.LOADING, 3.0),  # user script loading
            (ProcedureState.IDLE, 4.0),  # user script loaded
            (ProcedureState.RUNNING, 5.0),  # init called
            (ProcedureState.READY, 6.0),  # init complete
        ],
        stacktrace=None,
    ),
    state=ProcedureState.READY,
)

# Valid JSON struct for creating a new procedure
CREATE_GIT_JSON = dict(
    script={
        "script_type": "git",
        "script_uri": "git:///test.py",
        "create_env": True,
        "git_args": dict(git_repo="http://foo.git", git_branch="main"),
    },
    script_args={"init": dict(args=(1, 2, 3), kwargs=dict(kw1="a", kw2="b"))},
)

# object expected to be returned when creating the Procedure defined above
CREATE_GIT_SUMMARY = ProcedureSummary(
    id=1,
    script=GitScript(
        "git:///test.py",
        git_args=GitArgs(git_repo="http://foo.git", git_branch="main"),
        create_env=True,
    ),
    script_args=[
        ArgCapture(fn="init", fn_args=ProcedureInput(1, 2, 3, kw1="a", kw2="b"), time=1)
    ],
    history=ProcedureHistory(
        process_states=[
            (ProcedureState.CREATING, 1.0),  # process starting
            (ProcedureState.IDLE, 2.0),  # process created
            (ProcedureState.LOADING, 3.0),  # user script loading
            (ProcedureState.IDLE, 4.0),  # user script loaded
            (ProcedureState.RUNNING, 5.0),  # init called
            (ProcedureState.READY, 6.0),  # init complete
        ],
        stacktrace=None,
    ),
    state=ProcedureState.READY,
)

ABORT_JSON = dict(state="STOPPED", abort=True)

# Valid JSON struct for starting a prepared procedure
RUN_JSON = dict(
    script_uri="file:///test.py",
    script_args={"main": dict(args=(4, 5, 6), kwargs=dict(kw3="c", kw4="d"))},
    state="RUNNING",
)

# object expected to be returned when the procedure is executed
RUN_SUMMARY = ProcedureSummary(
    id=1,
    script=FileSystemScript("file:///test.py"),
    script_args=[
        ArgCapture(
            fn="init", fn_args=ProcedureInput(1, 2, 3, kw1="a", kw2="b"), time=1
        ),
        ArgCapture(
            fn="main", fn_args=ProcedureInput(4, 5, 6, kw3="c", kw4="d"), time=1
        ),
    ],
    history=ProcedureHistory(
        process_states=[
            (ProcedureState.CREATING, 1.0),  # process starting
            (ProcedureState.IDLE, 2.0),  # process created
            (ProcedureState.LOADING, 3.0),  # user script loading
            (ProcedureState.IDLE, 4.0),  # user script loaded
            (ProcedureState.RUNNING, 5.0),  # init called
            (ProcedureState.READY, 6.0),  # init complete
            (ProcedureState.RUNNING, 7.0),  # main called
        ],
        stacktrace=None,
    ),
    state=ProcedureState.RUNNING,
)

ACTIVITY_REQUEST = {
    "sbd_id": "sbi-001",
    "activity_name": "allocate",
    "script_args": {"main": {"args": [1], "kwargs": {"subarray_id": "42"}}},
    "prepare_only": False,
}

ACTIVITY_SUMMARY = ActivitySummary(
    id=1,
    pid=123,
    sbd_id="sbd-mvp01-20220923-00001",
    activity_name="allocate",
    prepare_only=False,
    script_args={},
    activity_states=[(ActivityState.TODO, 123)],
)

# resource partial URL for testing procedure execution with above JSON
RUN_ENDPOINT = f"{PROCEDURES_ENDPOINT}/{RUN_SUMMARY.id}"


class PubSubHelper:
    def __init__(self, spec=None, match_request_id=True):
        # client just wants to capture all messages, no responses required
        if spec is None:
            spec = {}

        messages = []
        self.messages = messages
        self.spec = spec
        self.match_request_id = match_request_id
        pub.subscribe(self.respond, pub.ALL_TOPICS)

    def respond(self, topic=pub.AUTO_TOPIC, **msg_data):
        topic_cls = self.get_topic_class(topics, topic.name)
        self.messages.append((topic, msg_data))

        if topic_cls in self.spec:
            (args, kwargs) = self.spec[topic_cls].pop(0)

            kwargs["msg_src"] = "PubSubHelper"
            if "request_id" in msg_data and self.match_request_id:
                kwargs["request_id"] = msg_data["request_id"]

            pub.sendMessage(*args, **kwargs)

    @property
    def topic_list(self):
        topic_list = [
            self.get_topic_class(topics, topic.name) for (topic, _) in self.messages
        ]
        return topic_list

    def __getitem__(self, key):
        return self.messages[key]

    def get_topic_class(self, module, cls):
        if not cls:
            return module
        s = cls.split(".")
        cls = getattr(module, s[0])
        return self.get_topic_class(cls, ".".join(s[1:]))

    def messages_on_topic(self, topic):
        return [
            msg
            for msg_topic, msg in self.messages
            if msg_topic.name == topic._topicNameStr
        ]

    def wait_for_message_on_topic(self, topic, timeout=1.0, tick=0.01):
        deadline = time.time() + timeout
        sleep_secs = tick
        len_before = len(self.messages_on_topic(topic))
        while len(self.messages_on_topic(topic)) == len_before and sleep_secs > 0:
            time.sleep(sleep_secs)
            sleep_secs = mptools._sleep_secs(tick, deadline)

    def wait_for_lifecycle(self, state, msg_src=None, timeout=1.0, tick=0.01) -> bool:
        """
        Timebound wait for a lifecycle state event to be received signifying a
        transition to the target state.

        Returns True if the event was received.
        """
        deadline = time.time() + timeout
        sleep_secs = tick

        if msg_src is None:

            def msg_src_matcher(m):
                return True

        else:

            def msg_src_matcher(m):
                return m.get("msg_src", None) == str(msg_src)

        def any_msgs_with_state():
            return any(
                True
                for m in self.messages_on_topic(topics.procedure.lifecycle.statechange)
                if m["new_state"] == state and msg_src_matcher(m)
            )

        while not any_msgs_with_state() and sleep_secs > 0:
            time.sleep(sleep_secs)
            sleep_secs = mptools._sleep_secs(tick, deadline)

        return any_msgs_with_state()

    def assert_state_history(self, pid: int, expected: List[ProcedureState]):
        """
        Assert that the state history of a Procedure is as expected.

        :param pid: PID of Procedure to inspect
        :param expected: ordered list of states for comparison
        """
        msgs = self.messages_on_topic(topics.procedure.lifecycle.statechange)
        states = [msg["new_state"] for msg in msgs if int(msg["msg_src"]) == pid]
        assert states == expected


def assert_json_equal_to_procedure_summary(
    summary: ProcedureSummary, summary_json: dict
):
    """
    Helper function to compare JSON against a reference ProcedureSummary
    instance. An assertion error will be raised if the JSON does not match.

    :param summary: reference ProcedureSummary instance
    :param summary_json: JSON for the ProcedureSummary
    """
    assert summary_json["uri"] == f"http://localhost/{PROCEDURES_ENDPOINT}/{summary.id}"
    assert summary_json["script"]["script_type"] == summary.script.get_type()
    assert summary_json["script"]["script_uri"] == summary.script.script_uri
    if summary_json["script"].get("git_args"):
        assert isinstance(summary.script, GitScript)
        assert (
            summary_json["script"]["git_args"]["git_repo"]
            == summary.script.git_args.git_repo
        )
        assert (
            summary_json["script"]["git_args"]["git_branch"]
            == summary.script.git_args.git_branch
        )
        assert (
            summary_json["script"]["git_args"]["git_commit"]
            == summary.script.git_args.git_commit
        )
    for args in summary.script_args:
        i: ProcedureInput = args.fn_args
        arg_dict = summary_json["script_args"][args.fn]
        assert i.args == tuple(arg_dict["args"])
        assert i.kwargs == arg_dict["kwargs"]
    assert summary_json["state"] == summary.state.name
    assert summary_json["history"]["stacktrace"] == summary.history.stacktrace
    for i, state in enumerate(summary.history.process_states):
        assert state[0].name == summary_json["history"]["process_states"][i][0]
        assert state[1] == summary_json["history"]["process_states"][i][1]
        assert isinstance(summary_json["history"]["process_states"][i][1], float)


def assert_json_equal_to_activity_summary(summary: ActivitySummary, summary_json: dict):
    """
    Helper function to compare JSON against a reference ActivitySummary
    instance. An assertion error will be raised if the JSON does not match.

    :param summary: reference ActivitySummary instance
    :param summary_json: JSON for the ProcedureSummary
    """
    assert summary_json["uri"] == f"http://localhost/{ACTIVITIES_ENDPOINT}/{summary.id}"
    assert summary_json["procedure_id"] == summary.pid
    assert summary_json["sbd_id"] == summary.sbd_id
    assert summary_json["activity_name"] == summary.activity_name
    assert summary_json["prepare_only"] == summary.prepare_only


@pytest.fixture(name="client")
def fixture_client():
    """
    Test fixture that returns a Flask application instance
    """
    app = restserver.create_app()
    app.config.update(TESTING=True)
    app.config.update(msg_src="unit tests")
    app.config.update(shutdown_event=threading.Event())
    # must create app_context for current_app to resolve correctly in SSE blueprint
    with app.app_context():
        with app.test_client() as client:
            yield client


@pytest.fixture(name="short_timeout")
def fixture_short_timeout():
    """
    Fixture to shorten grace period before timeout
    """
    timeout = restserver.TIMEOUT

    try:
        restserver.TIMEOUT = 0.1
        yield
    finally:
        restserver.TIMEOUT = timeout


# Tests for ProcedureAPI


def test_get_procedures_with_no_procedures_present_returns_empty_list(client):
    """
    Verify that listing resources returns an empty response when no procedures
    have been registered
    """
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(PROCEDURES_ENDPOINT)
    response_json = response.get_json()
    assert "procedures" in response_json
    assert response_json["procedures"] == []


def test_get_procedures_returns_expected_summaries(client):
    """
    Test that listing procedure resources returns the expected JSON payload
    """
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(PROCEDURES_ENDPOINT)
    assert response.status_code == 200
    response_json = response.get_json()
    assert "procedures" in response_json
    procedures_json = response_json["procedures"]
    assert len(procedures_json) == 1
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedures_json[0])


def test_get_procedure_by_id(client):
    """
    Verify that getting a resource by ID returns the expected JSON payload
    """
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{PROCEDURES_ENDPOINT}/{CREATE_SUMMARY.id}")
    assert response.status_code == HTTPStatus.OK

    response_json = response.get_json()
    assert "procedure" in response_json
    procedure_json = response_json["procedure"]
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedure_json)


def test_get_procedure_gives_404_for_invalid_id(client):
    """
    Verify that requesting an invalid resource returns an error.
    """
    # empty list as response shows that PID not found when trying to retrieve
    # procedure
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{PROCEDURES_ENDPOINT}/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response_json = response.get_json()
    assert response_json == {
        "error": "404 Not Found",
        "type": "ResourceNotFound",
        "Message": "No information available for PID=1",
    }


def test_successful_post_to_procedures_endpoint_returns_created_http_status(client):
    """
    Verify that creating a new Procedure returns the CREATED HTTP status code
    """
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(PROCEDURES_ENDPOINT, json=CREATE_JSON)
    assert response.status_code == HTTPStatus.CREATED


def test_successful_post_to_procedures_endpoint_returns_summary_in_response(client):
    """
    Verify that creating a new Procedure returns the expected JSON payload:
    a summary of the created Procedure.
    """
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(PROCEDURES_ENDPOINT, json=CREATE_JSON)
    response_json = response.get_json()

    assert "procedure" in response_json
    procedure_json = response_json["procedure"]
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedure_json)


def test_successful_post_to_procedures_endpoint_returns_git_summary_in_response(client):
    """
    Verify that creating a new Procedure returns the expected JSON payload:
    a summary of the created Procedure with git arguments.
    """
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_GIT_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(PROCEDURES_ENDPOINT, json=CREATE_GIT_JSON)
    response_json = response.get_json()

    assert "procedure" in response_json
    procedure_json = response_json["procedure"]
    assert_json_equal_to_procedure_summary(CREATE_GIT_SUMMARY, procedure_json)


def test_successful_post_to_procedures_endpoint_returns_git_summary_in_response_with_default_git_args(
    client,
):
    """
    Verify that creating a new Procedure returns the expected JSON payload:
    a summary of the created Procedure with default git arguments.
    """
    request_json = copy.deepcopy(CREATE_GIT_JSON)
    del request_json["script"]["git_args"]
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_GIT_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(PROCEDURES_ENDPOINT, json=request_json)
    response_json = response.get_json()

    assert "procedure" in response_json
    procedure_json = response_json["procedure"]
    assert_json_equal_to_procedure_summary(CREATE_GIT_SUMMARY, procedure_json)


def test_post_to_procedures_endpoint_requires_script_uri_json_parameter(client):
    """
    Verify that the script_uri must be present in the 'create procedure' JSON
    request.
    """
    malformed = copy.deepcopy(CREATE_JSON)
    del malformed["script"]["script_uri"]
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.BAD_REQUEST

    response_json = response.get_json()
    assert response_json == {
        "error": "400 Bad Request",
        "type": "Malformed Request",
        "Message": "Malformed script in request",
    }


def test_post_to_procedures_endpoint_unknown_script_type(client):
    """
    Verify that the script_uri must be present in the 'create procedure' JSON
    request.
    """
    malformed = copy.deepcopy(CREATE_JSON)
    malformed["script"]["script_type"] = "foo"
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.BAD_REQUEST

    response_json = response.get_json()
    assert response_json == {
        "error": "400 Bad Request",
        "type": "Malformed Request",
        "Message": "Script type foo not supported",
    }


def test_post_to_procedures_endpoint_requires_script_arg_be_a_dict(client):
    """
    Verify that the API checks the script_arg parameter is of the correct type
    """
    malformed = copy.deepcopy(CREATE_JSON)
    malformed["script_args"] = "junk"
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.BAD_REQUEST

    response_json = response.get_json()
    assert response_json == {
        "error": "400 Bad Request",
        "type": "Malformed Request",
        "Message": "Malformed script_args in request",
    }


def test_post_to_procedures_endpoint_sends_init_arguments(client):
    """
    Verify that constructor arguments are relayed correctly when creating a
    new Procedure.
    """
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_SUMMARY))
        ],
    }
    helper = PubSubHelper(spec)

    client.post(PROCEDURES_ENDPOINT, json=CREATE_JSON)

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.create,  # procedure creation requested
        topics.procedure.lifecycle.created,  # CREATED ProcedureSummary returned
    ]

    # now verify arguments were extracted from JSON and passed into command
    expected_cmd = PrepareProcessCommand(
        script=CREATE_SUMMARY.script,
        init_args=CREATE_SUMMARY.script_args[0].fn_args,
    )
    assert helper.messages[0][1]["cmd"] == expected_cmd


def test_post_to_procedures_endpoint_sends_git_arguments(client):
    """
    Verify that git arguments are relayed correctly when creating a
    new Procedure.
    """
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=CREATE_GIT_SUMMARY))
        ],
    }
    helper = PubSubHelper(spec)

    client.post(PROCEDURES_ENDPOINT, json=CREATE_GIT_JSON)

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.create,  # procedure creation requested
        topics.procedure.lifecycle.created,  # CREATED ProcedureSummary returned
    ]

    # now verify arguments were extracted from JSON and passed into command
    expected_cmd = PrepareProcessCommand(
        script=CREATE_GIT_SUMMARY.script,
        init_args=CREATE_SUMMARY.script_args[0].fn_args,
    )
    assert helper.messages[0][1]["cmd"] == expected_cmd


def test_post_to_procedures_endpoint_sends_default_git_arguments(client):
    """
    Verify that git arguments are relayed correctly when creating a
    new Procedure.
    """
    summary = copy.deepcopy(CREATE_GIT_SUMMARY)
    summary.script.git_args = GitArgs()
    spec = {
        topics.request.procedure.create: [
            ([topics.procedure.lifecycle.created], dict(result=summary))
        ],
    }
    helper = PubSubHelper(spec)

    summary_json = copy.deepcopy(CREATE_GIT_JSON)
    del summary_json["script"]["git_args"]

    client.post(PROCEDURES_ENDPOINT, json=summary_json)

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.create,  # procedure creation requested
        topics.procedure.lifecycle.created,  # CREATED ProcedureSummary returned
    ]

    # now verify arguments were extracted from JSON and passed into command
    expected_cmd = PrepareProcessCommand(
        script=GitScript(
            CREATE_GIT_SUMMARY.script.script_uri,  # pylint: disable=no-member
            git_args=GitArgs(),
            create_env=True,
        ),
        init_args=CREATE_GIT_SUMMARY.script_args[0].fn_args,
    )
    assert helper.messages[0][1]["cmd"] == expected_cmd


def test_put_procedure_returns_404_if_procedure_not_found(client):
    """
    Verify that PUT to a missing Procedure returns 404 NotFound.
    """
    # empty list in response signifies that PID was not found when requesting
    # ProcedureSummary
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[]))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(f"{PROCEDURES_ENDPOINT}/123")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response_json = response.get_json()
    assert response_json == {
        "error": "404 Not Found",
        "type": "ResourceNotFound",
        "Message": "No information available for PID=123",
    }

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # no procedure returned
    ]


def test_put_procedure_returns_error_if_no_json_supplied(client):
    """
    Verify that a PUT request requires a JSON payload
    """
    # The procedure is retrieved before the JSON is examined, hence we need to
    # prime the pubsub messages
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT)
    assert response.status_code == HTTPStatus.BAD_REQUEST

    response_json = response.get_json()
    assert response_json == {
        "error": "400 Bad Request",
        "type": "Empty Response",
        "Message": "No JSON available in response",
    }

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # procedure returned
    ]


def test_put_procedure_calls_run_on_execution_service(client):
    """
    Verify that the appropriate ScriptExecutionService methods are called
    when a valid 'start Procedure' PUT request is received
    """
    # Message sequence for starting a CREATED procedure is:
    # 1. request.procedure.list to retrieve the Procedure to inspect
    # 2. procedure.pool.list is sent with response = [ProcedureSummary]
    # Code sees old state is CREATED, required state is RUNNING
    # 3. request.procedure.start is sent to request procedure starts execution
    # 4. procedure.lifecycle.started response sent with list containing
    #    ProcedureSummary describing procedure which is now running
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
        topics.request.procedure.start: [
            ([topics.procedure.lifecycle.started], dict(result=RUN_SUMMARY))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=RUN_JSON)
    response_json = response.get_json()

    # verify RUNNING ProcedureSummary is contained in response JSON
    assert "procedure" in response_json
    assert_json_equal_to_procedure_summary(RUN_SUMMARY, response_json["procedure"])

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # procedure returned
        topics.request.procedure.start,  # procedure abort requested
        topics.procedure.lifecycle.started,  # procedure abort response
    ]

    # verify correct procedure was started
    expected_cmd = StartProcessCommand(
        process_uid=RUN_SUMMARY.id,
        fn_name="main",
        run_args=RUN_SUMMARY.script_args[1].fn_args,
    )
    assert helper.messages[2][1]["cmd"] == expected_cmd


def test_put_procedure_calls_stop_and_executes_abort_script(client):
    """
    Verify that the correct messages are sent when a valid request to stop and
    abort a running procedure is received.
    """
    # Message sequence for stopping a RUNNING procedure is:
    # 1. request.procedure.list to retrieve the Procedure to inspect
    # 2. procedure.pool.list is sent with response = [ProcedureSummary]
    # Code sees old state is RUNNING, required state is STOPPED
    # 3. request.procedure.stop is sent to request script abort
    # 4. procedure.lifecycle.stopped response sent with list containing
    #    ProcedureSummary for abort script which is now running
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[RUN_SUMMARY]))
        ],
        topics.request.procedure.stop: [
            ([topics.procedure.lifecycle.stopped], dict(result=[RUN_SUMMARY]))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=ABORT_JSON)
    response_json = response.get_json()

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # procedure returned
        topics.request.procedure.stop,  # procedure abort requested
        topics.procedure.lifecycle.stopped,  # procedure abort response
    ]

    # verify command payload - correct procedure should be stopped in step #3
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id, run_abort=True)
    assert helper.messages[2][1]["cmd"] == cmd

    assert "abort_message" in response_json
    expected_response = (
        "Successfully stopped script with ID 1 and aborted subarray activity"
    )
    assert response_json["abort_message"] == expected_response


def test_put_procedure_calls_stop_on_execution_service(client):
    """
    Verify that the correct messages are sent when a valid PUT request to stop
    but not abort a running procedure is received.
    """
    # Message sequence for stopping a RUNNING procedure is:
    # 1. request.procedure.list to retrieve the Procedure to inspect
    # 2. procedure.pool.list is sent with response = [ProcedureSummary]
    # - code sees old state is RUNNING, required state is STOPPED
    # 3. request.procedure.stop is sent to request script abort
    # 4. procedure.lifecycle.stopped response sent with empty list, showing no
    #    abort procedure is running
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[RUN_SUMMARY]))
        ],
        topics.request.procedure.stop: [
            ([topics.procedure.lifecycle.stopped], dict(result=[]))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=dict(state="STOPPED", abort=False))
    response_json = response.get_json()

    # verify message topic and order
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # procedure returned
        topics.request.procedure.stop,  # procedure abort requested
        topics.procedure.lifecycle.stopped,  # procedure abort response
    ]

    # correct procedure should be stopped
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id, run_abort=False)
    assert helper.messages[2][1]["cmd"] == cmd

    assert "abort_message" in response_json
    expected_response = "Successfully stopped script with ID 1"
    assert response_json["abort_message"] == expected_response


def test_put_procedure_does_not_start_a_procedure_unless_new_state_is_running(client):
    """
    Verify that a PUT request does not start execution if the new state is not
    RUNNING.
    """
    # Message sequence is:
    # 1. request.procedure.list to retrieve the Procedure to inspect
    # 2. procedure.pool.list is sent with response = [ProcedureSummary]
    # - code sees new state is not RUNNING, realises it's a no-op request
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    helper = PubSubHelper(spec)

    # Deleting 'state' from JSON makes the PUT request a no-op (=no transition
    # required)
    json = copy.deepcopy(RUN_JSON)
    del json["state"]
    _ = client.put(RUN_ENDPOINT, json=json)

    # assert that request to start a procedure was not broadcast
    assert topics.request.procedure.start not in helper.topic_list


def test_put_procedure_returns_procedure_summary(client):
    """
    Verify that PUT returns the expected JSON payload even if a state
    transition doesn't occur
    """
    # Message sequence is:
    # 1. request.procedure.list to retrieve the Procedure to inspect
    # 2. procedure.pool.list is sent with response = [ProcedureSummary]
    # - code sees new state is not RUNNING, realises it's a no-op request
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    # Deleting 'state' from JSON makes the operation a no-op (=no transition
    # required)
    json = copy.deepcopy(RUN_JSON)
    del json["state"]

    response = client.put(RUN_ENDPOINT, json=json)
    response_json = response.get_json()

    assert "procedure" in response_json
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json["procedure"])


def test_stopping_a_non_running_procedure_returns_appropriate_error_message(client):
    """
    Invalid procedure state transitions should result in an error.
    """
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=dict(state="STOPPED", abort=False))
    response_json = response.get_json()

    # verify message topic and order
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # procedure returned
    ]

    # correct procedure should be stopped
    assert "abort_message" in response_json
    expected_response = "Cannot stop script with ID 1: Script is not running"
    assert response_json["abort_message"] == expected_response


def test_giving_non_dict_script_args_returns_error_code(client):
    """
    script_args JSON parameter must be a dict, otherwise HTTP 500 is raised.
    """
    spec = {
        topics.request.procedure.list: [
            ([topics.procedure.pool.list], dict(result=[CREATE_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    json = dict(CREATE_JSON)
    json.update(script_args=["foo"])

    response = client.put(RUN_ENDPOINT, json=json)
    assert response.status_code == 400

    response_json = response.get_json()
    assert response_json == {
        "error": "400 Bad Request",
        "type": "Malformed Response",
        "Message": "Malformed script_args in response",
    }


def test_call_and_respond_aborts_with_timeout_when_no_response_received(
    client, short_timeout
):
    """
    HTTP 504 (Gateway Timeout) should be raised when message reception wait
    time exceeds timeout
    """
    # do not prime pubsub, so request will timeout
    response = client.get(PROCEDURES_ENDPOINT)
    # 504 and timeout error message
    assert response.status_code == 504

    response_json = response.get_json()
    assert response_json["error"] == "504 Gateway Timeout"
    assert response_json["Message"].startswith("Timeout waiting for msg ")
    assert response_json["type"] == "Timeout Error"


def test_call_and_respond_ignores_responses_when_request_id_differs():
    """
    Verify that the messages with different request IDs are ignored.
    """

    # call_and_respond will block the MainThread while waiting for its queue
    # to be filled with a result, hence we need to create another thread which
    # will broadcast messages as if it's the other component running
    # concurrently
    def publish():
        # sleep long enough for call_and_respond to start running
        time.sleep(0.1)
        for i in range(10):
            pub.sendMessage(
                topics.procedure.pool.list, msg_src="mock", request_id=123, result=i
            )
        pub.sendMessage(
            topics.procedure.pool.list, msg_src="mock", request_id=456, result="ok"
        )

    t = threading.Thread(target=publish)

    app = flask.Flask("test")
    with app.app_context():
        app.config = dict(msg_src="mock")

        # this sets the request ID to match to 'bar'
        with mock.patch("time.time_ns") as mock_time:
            mock_time.return_value = 456

            t.start()
            result = restserver.call_and_respond(
                topics.request.procedure.list, topics.procedure.pool.list
            )

    assert result == "ok"


def test_sse_string_messages_are_streamed_correctly(client):
    """
    Verify that simple Messages are streamed as SSE events correctly.
    """
    msg = restserver.Message("foo", type="message")

    with mock.patch(
        "ska_oso_oet.procedure.application.restserver.ServerSentEventsBlueprint.messages"
    ) as mock_messages:
        mock_messages.return_value = [msg]
        response = client.get("/api/v1.0/stream")

        assert isinstance(response, flask.Response)
        assert response.mimetype == "text/event-stream"
        assert response.status_code == 200
        assert response.is_streamed
        output = response.get_data(as_text=True)
        assert output == "\nevent:message\ndata:foo\n\n"


def test_sse_complex_messages_are_streamed_correctly(client):
    """
    Verify that Messages containing structured data are streamed correctly.
    """
    msg = restserver.Message({"foo": "bar"}, type="message", id=123)

    with mock.patch(
        "ska_oso_oet.procedure.application.restserver.ServerSentEventsBlueprint.messages"
    ) as mock_messages:
        mock_messages.return_value = [msg]
        response = client.get("/api/v1.0/stream")

        assert isinstance(response, flask.Response)
        assert response.mimetype == "text/event-stream"
        assert response.status_code == 200
        assert response.is_streamed
        output = response.get_data(as_text=True)
        assert output == '\nevent:message\ndata:{"foo": "bar"}\nid:123\n\n'


def test_sse_messages_returns_pubsub_messages(client):
    """
    Test that pypubsub messages are returned by SSE blueprint's messages method.
    """

    def publish():
        # sleep long enough for generator to start running
        time.sleep(0.1)
        pub.sendMessage(topics.scan.lifecycle.start, msg_src="foo", sb_id="bar")

    t = threading.Thread(target=publish)

    bp = client.application.blueprints["sse"]
    gen = bp.messages()
    assert isinstance(gen, types.GeneratorType)

    t.start()

    output = next(gen)
    assert output == restserver.Message(
        dict(topic="scan.lifecycle.start", msg_src="foo", sb_id="bar")
    )


def test_message_input_eq_works_as_expected():
    """
    Verify message equality
    """
    m1 = restserver.Message({"foo": "bar"})
    m2 = restserver.Message({"foo": "bar"})
    m3 = restserver.Message({"foo": "bar"}, type="message")
    assert m1 == m2
    assert m1 != m3
    assert m1 != object()


def test_message_str():
    """
    Verify that the str string for a Message is correctly formatted.
    """
    message = restserver.Message("foo", type="message", id=123, retry=100)
    assert str(message) == "event:message\ndata:foo\nid:123\nretry:100\n\n"


def test_message_input_accepts_expected_constructor_values():
    """
    Verify that message constructor accepts expected inputs.
    """
    message = restserver.Message("foo", type="message", id=123, retry=100)
    assert message.data == "foo"
    assert message.type == "message"
    assert message.id == 123
    assert message.retry == 100


def test_message_with_multiline_data():
    """
    Verify that message works with multiline data.
    """
    message = restserver.Message("foo\nbar")
    assert message.data == "foo\nbar"
    assert message.type is None
    assert message.id is None
    assert message.retry is None
    assert str(message) == "data:foo\ndata:bar\n\n"


def test_message_raise_exception_on_empty():
    """
    Verify that empty message() raise exception
    """
    with pytest.raises(TypeError):
        restserver.Message()  # pylint: disable=no-value-for-parameter


def test_message_with_simple_data():
    """
    Verify that message works with simple data.
    """
    message = restserver.Message("foo")
    assert message.data == "foo"
    assert message.type is None
    assert message.id is None
    assert message.retry is None
    assert str(message) == "data:foo\n\n"


def test_make_public_summary():
    with mock.patch("flask.url_for") as mock_url_fn:
        mock_url_fn.return_value = (
            f"http://localhost/api/v1.0/procedures/{CREATE_SUMMARY.id}"
        )
        summary_json = restserver.make_public_procedure_summary(CREATE_SUMMARY)
        assert_json_equal_to_procedure_summary(CREATE_SUMMARY, summary_json)


def test_make_public_summary_git_args():
    with mock.patch("flask.url_for") as mock_url_fn:
        mock_url_fn.return_value = (
            f"http://localhost/api/v1.0/procedures/{CREATE_GIT_SUMMARY.id}"
        )
        summary_json = restserver.make_public_procedure_summary(CREATE_GIT_SUMMARY)
        assert_json_equal_to_procedure_summary(CREATE_GIT_SUMMARY, summary_json)


# Tests for ActivityAPI


def test_get_activities_with_no_activities_present_returns_empty_list(client):
    """
    Verify that listing resources returns an empty response when no activities
    have been registered
    """
    spec = {
        topics.request.activity.list: [([topics.activity.pool.list], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(ACTIVITIES_ENDPOINT)
    response_json = response.get_json()
    assert "activities" in response_json
    assert response_json["activities"] == []


def test_get_activities_returns_expected_summaries(client):
    """
    Test that listing activities resources returns the expected JSON payload
    """
    spec = {
        topics.request.activity.list: [
            ([topics.activity.pool.list], dict(result=[ACTIVITY_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(ACTIVITIES_ENDPOINT)
    assert response.status_code == 200
    response_json = response.get_json()
    assert "activities" in response_json
    activities_json = response_json["activities"]
    assert len(activities_json) == 1
    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, activities_json[0])


def test_get_activity_by_id(client):
    """
    Verify that getting a resource by ID returns the expected JSON payload
    """
    spec = {
        topics.request.activity.list: [
            ([topics.activity.pool.list], dict(result=[ACTIVITY_SUMMARY]))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{ACTIVITIES_ENDPOINT}/{ACTIVITY_SUMMARY.id}")
    assert response.status_code == HTTPStatus.OK

    response_json = response.get_json()
    assert "activity" in response_json
    activity_json = response_json["activity"]
    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, activity_json)


def test_get_activity_gives_404_for_invalid_id(client):
    """
    Verify that requesting an invalid resource returns an error.
    """
    # empty list as response shows that ID not found when trying to retrieve
    # activity
    spec = {
        topics.request.activity.list: [([topics.activity.pool.list], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(f"{ACTIVITIES_ENDPOINT}/1")
    assert response.status_code == HTTPStatus.NOT_FOUND

    response_json = response.get_json()
    assert response_json == {
        "error": "404 Not Found",
        "type": "ResourceNotFound",
        "Message": "No information available for ID=1",
    }


def test_successful_post_to_activities_endpoint_returns_ok_http_status(client):
    """
    Verify that creating a new Activity returns the OK HTTP status code
    """
    spec = {
        topics.request.activity.run: [
            ([topics.activity.lifecycle.running], dict(result=ACTIVITY_SUMMARY))
        ],
    }
    _ = PubSubHelper(spec)

    response = client.post(ACTIVITIES_ENDPOINT, json=ACTIVITY_REQUEST)
    assert response.status_code == HTTPStatus.CREATED


def test_successful_post_to_activities_endpoint_returns_summary_in_response(client):
    """
    Verify that posting a new Activity returns the expected JSON payload:
    a summary of the created Procedure.
    """
    spec = {
        topics.request.activity.run: [
            ([topics.activity.lifecycle.running], dict(result=ACTIVITY_SUMMARY))
        ],
    }
    helper = PubSubHelper(spec)

    response = client.post(ACTIVITIES_ENDPOINT, json=ACTIVITY_REQUEST)
    response_json = response.get_json()

    cmd: ActivityCommand = helper.messages_on_topic(topics.request.activity.run)[0][
        "cmd"
    ]

    assert cmd.script_args == {"main": ProcedureInput(1, subarray_id="42")}

    assert "activity" in response_json
    procedure_json = response_json["activity"]
    assert_json_equal_to_activity_summary(ACTIVITY_SUMMARY, procedure_json)

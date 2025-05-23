"""
Unit tests for the ska_oso_oet.procedure.ui package.
"""
import copy
from http import HTTPStatus

from ska_oso_oet.event import topics
from ska_oso_oet.procedure.application import (
    ArgCapture,
    PrepareProcessCommand,
    ProcedureHistory,
    ProcedureSummary,
    StartProcessCommand,
    StopProcessCommand,
)
from ska_oso_oet.procedure.domain import (
    FileSystemScript,
    GitScript,
    ProcedureInput,
    ProcedureState,
)
from ska_oso_oet.procedure.gitmanager import GitArgs
from tests.unit.conftest import PROCEDURES_ENDPOINT

from ..test_ui import PubSubHelper

# Valid JSON struct for creating a new procedure
CREATE_JSON = dict(
    script={"script_type": "filesystem", "script_uri": "file:///test.py"},
    script_args={"init": dict(args=(1, 2, 3), kwargs=dict(kw1="a", kw2="b"))},
)

# object expected to be returned when creating the Procedure defined above
CREATE_SUMMARY = ProcedureSummary(
    id=1,
    script=FileSystemScript(script_uri="file:///test.py"),
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
        script_uri="git:///test.py",
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
    script=FileSystemScript(script_uri="file:///test.py"),
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

# resource partial URL for testing procedure execution with above JSON
RUN_ENDPOINT = f"{PROCEDURES_ENDPOINT}/{RUN_SUMMARY.id}"


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
    response_json = response.json()
    assert len(response_json) == 1
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json[0])


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

    response_json = response.json()
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json)


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

    response_json = response.json()
    assert response_json == {
        "detail": "No information available for PID=1",
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
    response_json = response.json()

    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json)


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
    response_json = response.json()

    assert_json_equal_to_procedure_summary(CREATE_GIT_SUMMARY, response_json)


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
    response_json = response.json()

    assert_json_equal_to_procedure_summary(CREATE_GIT_SUMMARY, response_json)


def test_post_to_procedures_endpoint_requires_script_uri_json_parameter(client):
    """
    Verify that the script_uri must be present in the 'create procedure' JSON
    request.
    """
    malformed = copy.deepcopy(CREATE_JSON)
    del malformed["script"]["script_uri"]
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    response_json = response.json()
    assert response_json == {
        "detail": [
            {
                "input": {"script_type": "filesystem"},
                "loc": ["body", "script", "filesystem", "script_uri"],
                "msg": "Field required",
                "type": "missing",
            }
        ]
    }


def test_post_to_procedures_endpoint_unknown_script_type(client):
    """
    Verify that the script_uri must be present in the 'create procedure' JSON
    request.
    """
    malformed = copy.deepcopy(CREATE_JSON)
    malformed["script"]["script_type"] = "foo"
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert (
        "Input tag 'foo' found using 'script_type' does not match any of the expected"
        " tags: 'filesystem', 'git'"
        in response.text
    )


def test_post_to_procedures_endpoint_requires_script_arg_be_a_dict(client):
    """
    Verify that the API checks the script_arg parameter is of the correct type
    """
    malformed = copy.deepcopy(CREATE_JSON)
    malformed["script_args"] = "junk"
    response = client.post(PROCEDURES_ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert "Input should be a valid dictionary or object to extract" in response.text


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
            script_uri=CREATE_GIT_SUMMARY.script.script_uri,
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

    response = client.put(f"{PROCEDURES_ENDPOINT}/123", json=RUN_JSON)
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text

    response_json = response.json()
    assert response_json == {
        "detail": "No information available for PID=123",
    }

    # verify message sequence and topics
    assert helper.topic_list == [
        topics.request.procedure.list,  # procedure retrieval requested
        topics.procedure.pool.list,  # no procedure returned
    ]


def test_put_procedure_returns_error_if_no_json_supplied(client):
    """
    Verify that a PUT request requires a JSON payload. This will be validated against the Pydantic models
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
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert (
        """[{"type":"missing","loc":["body"],"msg":"Field required","input":null}]"""
        in response.text
    )

    # The Pydantic validation will fail before the update_procedure call is made, so no messages will be sent to topics
    assert helper.topic_list == []


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
    assert response.status_code == HTTPStatus.OK
    response_json = response.json()

    # verify RUNNING ProcedureSummary is contained in response JSON
    assert_json_equal_to_procedure_summary(RUN_SUMMARY, response_json)

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
    assert response.status_code == HTTPStatus.OK, response.text
    response_json = response.json()

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
    assert response.status_code == HTTPStatus.OK, response.text
    response_json = response.json()

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
    assert response.status_code == HTTPStatus.OK, response.text
    response_json = response.json()

    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json)


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
    assert response.status_code == HTTPStatus.OK, response.text
    response_json = response.json()

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
    script_args JSON parameter must match the Pydantic model, otherwise HTTP 422 is raised by FasyAPI.
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
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    assert "Input should be a valid dictionary or object to extract" in response.text


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
    response_json = response.json()
    assert response_json == []


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
        assert i.args == arg_dict["args"]
        assert i.kwargs == arg_dict["kwargs"]
    assert summary_json["state"] == summary.state.name
    assert summary_json["history"]["stacktrace"] == summary.history.stacktrace
    for i, state in enumerate(summary.history.process_states):
        assert state[0].name == summary_json["history"]["process_states"][i][0]
        assert state[1] == summary_json["history"]["process_states"][i][1]
        assert isinstance(summary_json["history"]["process_states"][i][1], float)

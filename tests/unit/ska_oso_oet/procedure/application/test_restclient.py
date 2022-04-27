# pylint: disable=W1510
# - W1510(subprocess-run-check) - not an issue - this is a test
"""
Unit tests for the REST client module.
"""
import subprocess
import unittest.mock as mock
from http import HTTPStatus

import fire
import requests_mock
from pytest import raises
from sseclient import Event, SSEClient

import ska_oso_oet
from ska_oso_oet.procedure.application.restclient import (
    ProcedureSummary,
    RestAdapter,
    RestClientUI,
)

PROCEDURES_URI = "http://localhost:5000/api/v1.0/procedures"

CREATE_PROCESS_RESPONSE = {
    "procedure": {
        "script_args": {
            "init": {
                "args": [],
                "kwargs": {
                    "sb_uri": "file:///path/to/scheduling_block_123.json",
                    "subarray": 1,
                },
            },
            "run": {"args": [], "kwargs": {}},
        },
        "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py",
        },
        "history": {
            "stacktrace": None,
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
            ],
        },
        "state": "READY",
        "uri": "http://localhost:5000/api/v1.0/procedures/2",
    }
}

LIST_PROCEDURES_NULL_RESPONSE = dict(procedures=[])

LIST_PROCEDURES_POSITIVE_RESPONSE = {
    "procedures": [
        {
            "script_args": {
                "init": {
                    "args": [],
                    "kwargs": {
                        "sb_uri": "file:///path/to/scheduling_block_123.json",
                        "subarray": 1,
                    },
                },
                "run": {"args": [], "kwargs": {"scan_duration": 14}},
            },
            "script": {
                "script_type": "filesystem",
                "script_uri": "file:///path/to/observing_script.py",
            },
            "history": {
                "stacktrace": None,
                "process_states": [
                    ["CREATING", 1601303225.8232567],
                    ["IDLE", 1601303225.8234567],
                    ["LOADING", 1601303225.8234767],
                    ["IDLE", 1601303225.8234796],
                    ["RUNNING", 1601303225.8234824],
                    ["READY", 1601303225.8234867],
                    ["RUNNING", 1601303225.8702714],
                ],
            },
            "state": "RUNNING",
            "uri": "http://localhost:5000/api/v1.0/procedures/1",
        }
    ]
}

PROCEDURE_POSITIVE_RESPONSE = {
    "procedure": {
        "script_args": {
            "init": {
                "args": [],
                "kwargs": {
                    "sb_uri": "file:///path/to/scheduling_block_123.json",
                    "subarray": 1,
                },
            },
            "run": {"args": [], "kwargs": {"scan_duration": 14}},
        },
        "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py",
        },
        "history": {
            "stacktrace": None,
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["CREATED", 1601303225.8234567],
                ["RUNNING", 1601303225.8702714],
            ],
        },
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/1",
    }
}

START_PROCESS_RESPONSE = {
    "procedure": {
        "script_args": {
            "init": {
                "args": [],
                "kwargs": {
                    "sb_uri": "file:///path/to/scheduling_block_123.json",
                    "subarray": 1,
                },
            },
            "run": {"args": [], "kwargs": {"scan_duration": 14}},
        },
        "script": {
            "script_type": "filesystem",
            "script_uri": "file:///path/to/observing_script.py",
        },
        "history": {
            "stacktrace": None,
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
            ],
        },
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/1",
    }
}

STOP_PROCESS_RESPONSE = {"abort_message": "Successfully stopped script with ID 1"}

STOP_PROCESS_AND_ABORT_SUBARRAY_ACTIVITY_RESPONSE = {
    "abort_message": (
        "Successfully stopped script with ID 1 and aborted subarray activity"
    )
}


# Tests for the RestAdapter


def test_json_payload_for_list_all_procedures_is_empty():
    """Ensure the payload for list does not exist"""
    with requests_mock.Mocker() as mock_server:
        mock_server.get(PROCEDURES_URI, json=LIST_PROCEDURES_NULL_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        _ = adapter.list()

        last_request = mock_server.last_request

    # check that the request payload does not exist
    assert last_request.method == "GET"
    assert last_request.text is None


def test_list_procedures_converts_no_procedures_response():
    """
    An empty list should be returned when no procedures are present
    """
    with requests_mock.Mocker() as mock_server:
        mock_server.get(PROCEDURES_URI, json=LIST_PROCEDURES_NULL_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        procedures = adapter.list()

    assert not procedures


def test_list_procedures_converts_procedures_present_response():
    """
    A list of ProcedureSummaries object should be returned when procedures
    are present.
    """
    expected = ProcedureSummary.from_json(
        LIST_PROCEDURES_POSITIVE_RESPONSE["procedures"][0]
    )

    with requests_mock.Mocker() as mock_server:
        mock_server.get(PROCEDURES_URI, json=LIST_PROCEDURES_POSITIVE_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        procedures = adapter.list()

    assert len(procedures) == 1
    assert procedures[0] == expected


def test_list_procedures_converts_procedure_present_response():
    """
    A list of with a single ProcedureSummary object should be returned when a procedure
    with the requested pid is present.
    """
    expected = ProcedureSummary.from_json(PROCEDURE_POSITIVE_RESPONSE["procedure"])

    with requests_mock.Mocker() as mock_server:
        mock_server.get(f"{PROCEDURES_URI}/1", json=PROCEDURE_POSITIVE_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        procedures = adapter.list(pid=1)

    assert len(procedures) == 1
    assert procedures[0] == expected


def test_list_process_raises_exception_for_wrong_status():
    """
    An Exception should be raised if the HTTP response status is not OK
    """
    with requests_mock.Mocker() as mock_server:
        mock_server.get(
            f"{PROCEDURES_URI}/1",
            json={"errorMessage": "some error"},
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

        client = RestAdapter(PROCEDURES_URI)
        with raises(Exception) as e:
            client.list(1)
        assert ("""{"errorMessage": "some error"}""",) == e.value.args


def test_create_procedure_raises_error_for_incorrect_script_prefix():
    """Check that incorrect script prefix raises an error"""
    script_uri = "incorrectprefix://test_uri"

    adapter = RestAdapter(PROCEDURES_URI)
    with raises(Exception) as e:
        adapter.create(script_uri)
    assert "Script URI type not handled: incorrectprefix" in str(e)


def test_create_procedure_sends_expected_script_uri():
    """Check that the script uri is sent in the payload"""
    script_uri = "file://test_uri"

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(
            PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE, status_code=HTTPStatus.CREATED
        )

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.create(script_uri)

        last_request = mock_server.last_request

    request_payload = last_request.json()
    assert "script" in request_payload
    assert request_payload["script"]["script_uri"] == script_uri


def test_create_process_sends_empty_init_args_when_left_undefined_by_user():
    """Check that default script args are sent"""
    expected_script_args = {"init": dict(args=[], kwargs={})}

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(
            PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE, status_code=HTTPStatus.CREATED
        )

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.create("file://test_uri")

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == "POST"
    request_payload = last_request.json()
    assert "script_args" in request_payload
    assert request_payload["script_args"] == expected_script_args


def test_create_process_sends_script_args_when_defined_by_user():
    """Check that user-supplied script arguments are sent"""
    user_init_args = {"args": [3, 6, 9], "kwargs": {}}
    expected_script_args_payload = {"init": user_init_args}

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(
            PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE, status_code=HTTPStatus.CREATED
        )

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.create("file://script_uri", init_args=user_init_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == "POST"
    request_payload = last_request.json()
    assert "script_args" in request_payload
    assert request_payload["script_args"] == expected_script_args_payload


def test_create_process_raises_exception_for_wrong_status():
    """
    An Exception should be raised if the HTTP response status is not CREATED
    """
    with requests_mock.Mocker() as mock_server:
        mock_server.post(
            PROCEDURES_URI,
            json={"errorMessage": "some error"},
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

        client = RestAdapter(PROCEDURES_URI)
        with raises(Exception) as e:
            client.create("file://test_uri")
        assert ("""{"errorMessage": "some error"}""",) == e.value.args


def test_start_execute_sends_empty_run_args_when_undefined_by_user():
    """Check that default script args are sent"""
    expected_script_args_payload = {"run": {"args": [], "kwargs": {}}}

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f"{PROCEDURES_URI}/1", json=START_PROCESS_RESPONSE)

        client = RestAdapter(PROCEDURES_URI)
        client.start(1)
        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == "PUT"
    request_payload = last_request.json()
    assert "script_args" in request_payload
    assert request_payload["script_args"] == expected_script_args_payload


def test_start_execute_sends_correct_script_args_when_user_provides_arguments():
    """Check that user-supplied script arguments are sent"""
    user_args = dict(args=[1, 2, 3], kwargs=dict(kw1="a", kw2="b"))
    expected_script_args = {"run": user_args}

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f"{PROCEDURES_URI}/1", json=START_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.start(1, run_args=user_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == "PUT"
    request_payload = last_request.json()
    assert "script_args" in request_payload
    assert request_payload["script_args"] == expected_script_args


def test_start_process_raises_exception_for_wrong_status():
    """
    An Exception should be raised if the HTTP response status is not OK
    """
    with requests_mock.Mocker() as mock_server:
        mock_server.put(
            f"{PROCEDURES_URI}/1",
            json={"errorMessage": "some error"},
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

        # use the client to submit a START request
        client = RestAdapter(PROCEDURES_URI)
        with raises(Exception) as e:
            client.start(1)
        assert ("""{"errorMessage": "some error"}""",) == e.value.args


def test_stop_procedure_sends_correct_command():
    """Check that the correct command is sent in the payload"""
    procedure_id = 1

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(
            f"{PROCEDURES_URI}/1", json=STOP_PROCESS_RESPONSE, status_code=HTTPStatus.OK
        )

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.stop(procedure_id)

        last_request = mock_server.last_request

    assert last_request.method == "PUT"
    request_payload = last_request.json()
    assert "state" in request_payload
    assert request_payload["abort"] is True
    assert request_payload["state"] == "STOPPED"


def test_stop_procedure_sends_command_with_abort_true():
    """Check that the correct command is sent in the payload"""
    procedure_id = 1
    run_abort = True

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(
            f"{PROCEDURES_URI}/1",
            json=STOP_PROCESS_AND_ABORT_SUBARRAY_ACTIVITY_RESPONSE,
            status_code=HTTPStatus.OK,
        )

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.stop(procedure_id, run_abort)

        last_request = mock_server.last_request

    assert last_request.method == "PUT"
    request_payload = last_request.json()
    assert "state" in request_payload
    assert request_payload["abort"] is True
    assert request_payload["state"] == "STOPPED"


def test_stop_process_raises_exception_for_wrong_status():
    """
    An Exception should be raised if the HTTP response status is not OK
    """
    with requests_mock.Mocker() as mock_server:
        mock_server.put(
            f"{PROCEDURES_URI}/1",
            json={"errorMessage": "some error"},
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        )

        # use the client to submit a START request
        client = RestAdapter(PROCEDURES_URI)
        with raises(Exception) as e:
            client.stop(1)
        assert ("""{"errorMessage": "some error"}""",) == e.value.args


@mock.patch.object(SSEClient, "__init__")
@mock.patch.object(SSEClient, "__iter__")
def test_listen_yields_sse_events(mock_iterator, mock_init):
    mock_init.return_value = None
    mock_iterator.return_value = iter([Event(id=1234)])

    client = RestAdapter(PROCEDURES_URI)
    result = client.listen()

    assert next(result).id == 1234


# Tests for the RestClientUI


REST_ADAPTER_CREATE_RESPONSE = ProcedureSummary(
    id=1,
    uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
    script_args={
        "init": {"args": [], "kwargs": {"subarray_id": 1}},
        "run": {"args": [], "kwargs": {}},
    },
    script={
        "script_type": "filesystem",
        "script_uri": "file:///app/scripts/allocate.py",
    },
    history={
        "process_states": [
            ["CREATING", 1603381492.3060987],
        ],
        "stacktrace": None,
    },
    state="CREATING",
)
REST_ADAPTER_CREATE_RESPONSE_WITH_GIT_ARGS = ProcedureSummary(
    id=1,
    uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
    script_args={
        "init": {"args": [], "kwargs": {"subarray_id": 1}},
        "run": {"args": [], "kwargs": {}},
    },
    script={
        "script_uri": "git:///app/scripts/allocate.py",
        "script_type": "git",
        "git_args": {
            "git_repo": "http://foo.git",
            "git_branch": "main",
            "git_commit": "HEAD",
        },
    },
    history={
        "process_states": [
            ["CREATING", 1603381492.3060987],
        ],
        "stacktrace": None,
    },
    state="CREATING",
)

REST_ADAPTER_LIST_RESPONSE = [
    ProcedureSummary(
        id=1,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "git:///app/scripts/allocate.py",
            "script_type": "git",
            "git_args": {
                "git_repo": "http://foo.git",
                "git_branch": "main",
                "git_commit": "HEAD",
            },
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
            ],
            "stacktrace": None,
        },
        state="READY",
    ),
    ProcedureSummary(
        id=2,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/2",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "git:///app/scripts/allocate.py",
            "script_type": "git",
            "git_args": {
                "git_repo": "http://foo.git",
                "git_branch": "main",
                "git_commit": "HEAD",
            },
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
            ],
            "stacktrace": None,
        },
        state="READY",
    ),
]

REST_ADAPTER_LIST_RESPONSE_WITH_STACKTRACE = [
    ProcedureSummary(
        id=2,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "file:///app/scripts/allocate.py",
            "script_type": "filesystem",
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
                ["FAILED", 1601303225.8702714],
            ],
            "stacktrace": """Traceback (most recent call last):
  File "/app/ska_oso_oet/procedure/domain.py", line 132, in run
    self.user_module.main(*args, **kwargs)
  File "/app/scripts/allocate.py", line 47, in _main
    allocated = subarray.allocate(allocation)
  File "/app/ska_oso_oet/domain.py", line 363, in allocate
    allocated = observingtasks.allocate_resources(self, resources)
  File "/app/ska_oso_oet/observingtasks.py", line 352, in allocate_resources
    command = get_allocate_resources_command(subarray, resources)
  File "/app/ska_oso_oet/observingtasks.py", line 259, in get_allocate_resources_command
    request = get_allocate_resources_request(subarray, resources, template_request)
  File "/app/ska_oso_oet/observingtasks.py", line 228, in get_allocate_resources_request
    template_sdp_config = template_request.sdp_config
    AttributeError: 'NoneType' object has no attribute 'sdp_config'
""",
        },
        state="FAILED",
    )
]

REST_ADAPTER_LIST_RESPONSE_WITH_GIT_ARGS = [
    ProcedureSummary(
        id=1,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "git:///app/scripts/allocate.py",
            "script_type": "git",
            "git_args": {
                "git_repo": "http://foo.git",
                "git_branch": "main",
                "git_commit": "HEAD",
            },
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
            ],
            "stacktrace": None,
        },
        state="READY",
    ),
]

REST_ADAPTER_START_RESPONSE = ProcedureSummary(
    id=1,
    uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
    script_args={
        "init": {"args": [], "kwargs": {"subarray_id": 1}},
        "run": {"args": [], "kwargs": {}},
    },
    script={
        "script_uri": "file:///app/scripts/allocate.py",
        "script_type": "filesystem",
    },
    history={
        "process_states": [
            ["CREATING", 1601303225.8232567],
            ["IDLE", 1601303225.8234567],
            ["LOADING", 1601303225.8234767],
            ["IDLE", 1601303225.8234796],
            ["RUNNING", 1601303225.8234824],
            ["READY", 1601303225.8234867],
        ],
        "stacktrace": None,
    },
    state="READY",
)

REST_ADAPTER_LIST_RESPONSE_FOR_STOP = [
    ProcedureSummary(
        id=1,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "file:///app/scripts/test_working.py",
            "script_type": "filesystem",
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
            ],
            "stacktrace": None,
        },
        state="RUNNING",
    )
]

REST_ADAPTER_TWO_RUNNING_PROCEDURES = [
    ProcedureSummary(
        id=1,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "file:///app/scripts/test_working.py",
            "script_type": "filesystem",
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
            ],
            "stacktrace": None,
        },
        state="RUNNING",
    ),
    ProcedureSummary(
        id=2,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/2",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "file:///app/scripts/test_working.py",
            "script_type": "filesystem",
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
            ],
            "stacktrace": None,
        },
        state="RUNNING",
    ),
]

REST_ADAPTER_STOP_RESPONSE = [
    "Successfully stopped script with ID 1 and aborted subarray activity"
]

REST_ADAPTER_LIST_RESPONSE_FOR_DESCRIBE = [
    ProcedureSummary(
        id=1,
        uri="http://127.0.0.1:5000/api/v1.0/procedures/1",
        script_args={
            "init": {"args": [], "kwargs": {"subarray_id": 1}},
            "run": {"args": [], "kwargs": {}},
        },
        script={
            "script_uri": "file:///app/scripts/test_working.py",
            "script_type": "filesystem",
        },
        history={
            "process_states": [
                ["CREATING", 1601303225.8232567],
                ["IDLE", 1601303225.8234567],
                ["LOADING", 1601303225.8234767],
                ["IDLE", 1601303225.8234796],
                ["RUNNING", 1601303225.8234824],
                ["READY", 1601303225.8234867],
                ["RUNNING", 1601303225.8702714],
                ["COMPLETED", 1601303225.8702714],
            ],
            "stacktrace": None,
        },
        state="COMPLETED",
    )
]

REST_ADAPTER_LISTEN_RESPONSE = [
    Event(
        data='{"topic": "user.script.announce", "msg": "announced"}',
        event="some event",
        id=101,
    )
]


def parse_rest_create_list_response(resp):
    """Split the response from the REST API lines
    into columns

    Args:
        resp (string): [description]

    Returns:
        [rest_response_object]: [description]
    """
    rest_responses = []
    lines = resp.splitlines()
    del lines[0:2]
    del lines[-1]
    for line in lines:
        elements = line.split()
        rest_response_object = {
            "id": elements[0],
            "uri": elements[1],
            "creation time": str(elements[2] + " " + elements[3]),
            "state": elements[4],
        }
        rest_responses.append(rest_response_object)
    return rest_responses


def test_restclientui_returns_error_when_not_passed_an_invalid_command():
    restclient = ska_oso_oet.procedure.application.restclient.__file__
    result = subprocess.run(
        ["python3", restclient, "blah"], capture_output=True, text=True
    )

    assert bool(result.stdout) is False
    assert result.stderr.count("ERROR") == 1


@mock.patch.object(RestAdapter, "create")
def test_restclientui_creates_a_valid_script(mock_create_fn, capsys):
    mock_create_fn.return_value = REST_ADAPTER_CREATE_RESPONSE
    fire.Fire(RestClientUI, ["create", "file:///app/scripts/allocate.py"])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]["id"] == str(1)
    assert result[0]["uri"] == "file:///app/scripts/allocate.py"
    assert result[0]["creation time"] == "2020-10-22 15:44:52"
    assert result[0]["state"] == "CREATING"


@mock.patch.object(RestAdapter, "create")
def test_restclientui_creates_a_valid_script_with_git_args(mock_create_fn, capsys):
    mock_create_fn.return_value = REST_ADAPTER_CREATE_RESPONSE_WITH_GIT_ARGS
    fire.Fire(RestClientUI, ["create", "git:///app/scripts/allocate.py"])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]["id"] == str(1)
    assert result[0]["uri"] == "git:///app/scripts/allocate.py"
    assert result[0]["creation time"] == "2020-10-22 15:44:52"
    assert result[0]["state"] == "CREATING"


@mock.patch.object(RestAdapter, "create")
def test_restclientui_handles_create_error(mock_start_fn, capsys):
    mock_start_fn.side_effect = RuntimeError("Test Error")

    fire.Fire(RestClientUI, ["create", "file:///app/scripts/allocate.py"])
    captured = capsys.readouterr()

    assert "The server encountered a problem: Test Error" in captured.out


@mock.patch.object(RestAdapter, "list")
def test_restclientui_lists_output(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE
    fire.Fire(RestClientUI, ["list"])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]["id"] == str(1)
    assert result[1]["id"] == str(2)


@mock.patch.object(RestAdapter, "list")
def test_restclientui_handles_list_error(mock_list_fn, capsys):
    mock_list_fn.side_effect = RuntimeError("Test Error")

    fire.Fire(RestClientUI, ["list"])
    captured = capsys.readouterr()

    assert "The server encountered a problem: Test Error" in captured.out


@mock.patch.object(RestAdapter, "list")
def test_restclientui_start_output_when_nothing_to_start(mock_list_fn, capsys):
    mock_list_fn.return_value = []

    fire.Fire(RestClientUI, ["start", "--nolisten"])
    captured = capsys.readouterr()

    assert "No procedures to start" in captured.out


@mock.patch.object(RestAdapter, "start")
@mock.patch.object(RestAdapter, "list")
def test_restclientui_start_output_when_given_no_pid(
    mock_list_fn, mock_start_fn, capsys
):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE
    mock_start_fn.return_value = REST_ADAPTER_START_RESPONSE

    fire.Fire(RestClientUI, ["start", "--nolisten"])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]["state"] == "READY"
    mock_start_fn.assert_called_with(2, run_args={"args": (), "kwargs": {}})


@mock.patch.object(RestAdapter, "list")
def test_restclientui_start_output_when_last_created_script_has_failed(
    mock_list_fn, capsys
):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE_WITH_STACKTRACE

    fire.Fire(RestClientUI, ["start", "--nolisten"])
    captured = capsys.readouterr()

    assert (
        "The last procedure created is in FAILED state and cannot be started"
        in captured.out
    )


@mock.patch.object(RestAdapter, "start")
@mock.patch.object(RestAdapter, "list")
def test_restclientui_start_output_when_given_pid(mock_list_fn, mock_start_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE
    mock_start_fn.return_value = REST_ADAPTER_START_RESPONSE

    fire.Fire(RestClientUI, ["start", "--pid=1", "--nolisten"])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]["id"] == str(1)
    assert result[0]["state"] == "READY"
    mock_start_fn.assert_called_with(1, run_args={"args": (), "kwargs": {}})


@mock.patch.object(RestAdapter, "listen")
@mock.patch.object(RestAdapter, "start")
@mock.patch.object(RestAdapter, "list")
def test_restclientui_start_and_listen_output_with_event(
    mock_list_fn, mock_start_fn, mock_listen_fn, capsys
):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE
    mock_start_fn.return_value = REST_ADAPTER_START_RESPONSE
    mock_listen_fn.return_value = REST_ADAPTER_LISTEN_RESPONSE

    fire.Fire(RestClientUI, ["start", "--pid=1", "--listen"])
    captured = capsys.readouterr()
    sections = captured.out.split("\nEvents\n------\n\n")
    processes = parse_rest_create_list_response(sections[0])
    event = sections[1]

    assert "Script message: announced" in event
    assert processes[0]["id"] == str(1)
    assert processes[0]["state"] == "READY"
    mock_start_fn.assert_called_once_with(1, run_args={"args": (), "kwargs": {}})
    mock_listen_fn.assert_called_once()


@mock.patch.object(RestAdapter, "start")
@mock.patch.object(RestAdapter, "list")
def test_restclientui_handles_start_error(mock_list_fn, mock_start_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE
    mock_start_fn.side_effect = RuntimeError("Test Error")

    fire.Fire(RestClientUI, ["start", "--pid=1", "--nolisten"])
    captured = capsys.readouterr()

    assert "The server encountered a problem: Test Error" in captured.out


@mock.patch.object(RestAdapter, "listen")
def test_restclientui_handles_listen_error(mock_listen_fn, capsys):
    mock_listen_fn.side_effect = RuntimeError(
        '{"type":"test", "Message":"this is a test error", "error":"TestError"}'
    )

    fire.Fire(RestClientUI, ["listen", "--topics=request.procedure.create"])
    captured = capsys.readouterr()

    assert (
        "Server encountered error TestError:   test: this is a test error\n"
        == captured.out
    )


@mock.patch.object(RestAdapter, "listen")
def test_restclientui_handles_listen_event_parse_error(mock_listen_fn, capsys):
    mock_listen_fn.return_value = [Event(data="")]
    fire.Fire(RestClientUI, ["listen", "--topics=request.procedure.create"])
    captured = capsys.readouterr()
    assert "" == captured.out

    mock_listen_fn.return_value = [Event(data="{'invalid json'}")]
    fire.Fire(RestClientUI, ["listen", "--topics=request.procedure.create"])
    captured = capsys.readouterr()
    assert "- ERROR Could not parse event: {'invalid json'}\n" == captured.out

    mock_listen_fn.return_value = [
        Event(data='{"topic": "this is not correct topic "}')
    ]
    fire.Fire(RestClientUI, ["listen", "--topics=request.procedure.create"])
    captured = capsys.readouterr()
    assert "" == captured.out

    # tests the case where the formatter returns a KeyError
    mock_listen_fn.return_value = [Event(data='{"topic": "subarray.fault"}')]
    fire.Fire(RestClientUI, ["listen", "--topics=subarray.fault"])
    captured = capsys.readouterr()
    assert "" == captured.out


@mock.patch.object(RestAdapter, "listen")
def test_restclientui_handles_listen_keyboard_interrupt(mock_listen_fn, capsys):
    mock_listen_fn.side_effect = KeyboardInterrupt()

    fire.Fire(RestClientUI, ["listen", "--topics=request.procedure.create"])
    captured = capsys.readouterr()

    assert not captured.out


@mock.patch.object(RestAdapter, "stop")
@mock.patch.object(RestAdapter, "list")
def test_restclientui_stop_output_when_a_script_is_running(
    mock_list_fn, mock_stop_fn, capsys
):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE_FOR_STOP
    mock_stop_fn.return_value = REST_ADAPTER_STOP_RESPONSE

    fire.Fire(RestClientUI, ["stop"])
    captured = capsys.readouterr()

    assert (
        "Successfully stopped script with ID 1 and aborted subarray activity"
        in captured.out
    )
    mock_stop_fn.assert_called_with(1, True)


@mock.patch.object(RestAdapter, "list")
def test_restclientui_stop_output_when_a_script_is_not_running(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE

    fire.Fire(RestClientUI, ["stop"])
    captured = capsys.readouterr()

    assert "No procedures to stop" in captured.out


@mock.patch.object(RestAdapter, "list")
def test_restclientui_stop_output_when_two_scripts_are_running(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_TWO_RUNNING_PROCEDURES

    fire.Fire(RestClientUI, ["stop"])
    captured = capsys.readouterr()

    assert (
        "WARNING: More than one procedure is running. Specify ID of the procedure to"
        " stop."
        in captured.out
    )


@mock.patch.object(RestAdapter, "stop")
def test_restclientui_handles_stop_error(mock_stop_fn, capsys):
    mock_stop_fn.side_effect = RuntimeError("Test Error")

    fire.Fire(RestClientUI, ["stop", "--pid=1"])
    captured = capsys.readouterr()

    assert "The server encountered a problem: Test Error" in captured.out


@mock.patch.object(RestAdapter, "list")
def test_restclientui_describe_when_stacktrace_present(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE_WITH_STACKTRACE

    fire.Fire(RestClientUI, ["describe", "--pid=2"])
    captured = capsys.readouterr()
    lines = captured.out.split("\n")

    assert "AttributeError" in captured.out
    assert "FAILED" in lines[13]
    mock_list_fn.assert_called_with(2)


@mock.patch.object(RestAdapter, "list")
def test_restclientui_describe_when_stacktrace_not_present(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE_FOR_DESCRIBE

    fire.Fire(RestClientUI, ["describe"])
    captured = capsys.readouterr()
    lines = captured.out.split("\n")

    assert "COMPLETED" in lines[13]
    mock_list_fn.assert_called_with(1)
    assert mock_list_fn.call_count == 2


@mock.patch.object(RestAdapter, "list")
def test_restclientui_describe_when_git_args_present(mock_list_fn, capsys):
    mock_list_fn.return_value = REST_ADAPTER_LIST_RESPONSE_WITH_GIT_ARGS

    fire.Fire(RestClientUI, ["describe"])
    captured = capsys.readouterr()
    lines = captured.out.split("\n")
    assert "Repository" in captured.out
    assert "http://foo.git" in lines[20]
    assert "main" in lines[20]
    assert "HEAD" in lines[20]
    mock_list_fn.assert_called_with(1)


@mock.patch.object(RestAdapter, "list")
def test_restclientui_describe_when_no_procedures(mock_list_fn, capsys):
    mock_list_fn.return_value = []

    fire.Fire(RestClientUI, ["describe"])
    captured = capsys.readouterr()

    assert "No procedures to describe" in captured.out


@mock.patch.object(RestAdapter, "list")
def test_restclientui_handles_describe_error(mock_list_fn, capsys):
    mock_list_fn.side_effect = RuntimeError("Test Error")

    fire.Fire(RestClientUI, ["describe", "--pid=1"])
    captured = capsys.readouterr()

    assert "The server encountered a problem: Test Error" in captured.out

"""
Unit tests for the REST client module.
"""
from http import HTTPStatus

import requests_mock

from oet.procedure.application.restclient import ProcedureSummary, RestAdapter

PROCEDURES_URI = 'http://localhost:5000/api/v1.0/procedures'

CREATE_PROCESS_RESPONSE = {
    "procedure": {
        "script_args": {
            "init": {
                "args": [],
                "kwargs": {
                    "sb_uri": "file:///path/to/scheduling_block_123.json",
                    "subarray": 1
                }
            },
            "run": {
                "args": [],
                "kwargs": {}
            }
        },
        "script_uri": "file:///path/to/observing_script.py",
        "state": "READY",
        "uri": "http://localhost:5000/api/v1.0/procedures/2"
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
                        "subarray": 1
                    }
                },
                "run": {
                    "args": [],
                    "kwargs": {
                        "scan_duration": 14
                    }
                }
            },
            "script_uri": "file:///path/to/observing_script.py",
            "state": "RUNNING",
            "uri": "http://localhost:5000/api/v1.0/procedures/1"
        }
    ]
}

START_PROCESS_RESPONSE = {
    "procedure": {
        "script_args": {
            "init": {
                "args": [],
                "kwargs": {
                    "sb_uri": "file:///path/to/scheduling_block_123.json",
                    "subarray": 1
                }
            },
            "run": {
                "args": [],
                "kwargs": {
                    "scan_duration": 14
                }
            }
        },
        "script_uri": "file:///path/to/observing_script.py",
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/1"
    }
}


def test_json_payload_for_list_all_procedures_is_empty():
    """Ensure the payload for list does not exist"""
    with requests_mock.Mocker() as mock_server:
        mock_server.get(PROCEDURES_URI, json=LIST_PROCEDURES_NULL_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        _ = adapter.list()

        last_request = mock_server.last_request

    # check that the request payload does not exist
    assert last_request.method == 'GET'
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
    expected = ProcedureSummary.from_json(LIST_PROCEDURES_POSITIVE_RESPONSE['procedures'][0])

    with requests_mock.Mocker() as mock_server:
        mock_server.get(PROCEDURES_URI, json=LIST_PROCEDURES_POSITIVE_RESPONSE)

        # use the client to submit a CREATE request
        adapter = RestAdapter(PROCEDURES_URI)
        procedures = adapter.list()

    assert len(procedures) == 1
    assert procedures[0] == expected


def test_create_procedure_sends_expected_script_uri():
    """Check that the script uri is sent in the payload"""
    script_uri = 'test_uri'

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE,
                         status_code=HTTPStatus.CREATED)

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.create(script_uri)

        last_request = mock_server.last_request

    request_payload = last_request.json()
    assert 'script_uri' in request_payload
    assert request_payload['script_uri'] == script_uri


def test_create_process_sends_empty_init_args_when_left_undefined_by_user():
    """Check that default script args are sent"""
    expected_script_args = {
        'init': dict(args=[], kwargs={})
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE,
                         status_code=HTTPStatus.CREATED)

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.create('test_uri')

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'POST'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args


def test_create_process_sends_script_args_when_defined_by_user():
    """Check that user-supplied script arguments are sent"""
    user_init_args = {
        'args': [3, 6, 9],
        'kwargs': {}
    }
    expected_script_args_payload = {
        'init': user_init_args
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post(PROCEDURES_URI, json=CREATE_PROCESS_RESPONSE,
                         status_code=HTTPStatus.CREATED)

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.create('script_uri', init_args=user_init_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'POST'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args_payload


def test_start_execute_sends_empty_run_args_when_undefined_by_user():
    """Check that default script args are sent"""
    expected_script_args_payload = {
        'run': {
            'args': [],
            'kwargs': {}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f'{PROCEDURES_URI}/1', json=START_PROCESS_RESPONSE)

        client = RestAdapter(PROCEDURES_URI)
        client.start(1)
        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args_payload


def test_start_execute_sends_correct_script_args_when_user_provides_arguments():
    """Check that user-supplied script arguments are sent"""
    user_args = dict(args=[1, 2, 3], kwargs=dict(kw1='a', kw2='b'))
    expected_script_args = {
        'run': user_args
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f'{PROCEDURES_URI}/1', json=START_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestAdapter(PROCEDURES_URI)
        client.start(1, run_args=user_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args


def test_stop_procedure_sends_correct_command():
    """Check that the correct command is sent in the payload"""
    procedure_id = 1

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f'{PROCEDURES_URI}/1', json={},
                        status_code=HTTPStatus.OK)

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.stop(procedure_id)

        last_request = mock_server.last_request

    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'state' in request_payload
    assert request_payload['state'] == 'STOP'


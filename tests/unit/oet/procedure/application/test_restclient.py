"""
Unit tests for the REST client module.
"""
from http import HTTPStatus

import requests_mock
import unittest.mock as mock
import fire

import os
import subprocess
import oet

from oet.procedure.application.restclient import ProcedureSummary, RestAdapter, RestClientUI

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
        "history": {
            "stacktrace": None,
            "process_states": {
                "CREATED": 1601303225.8702714
            }
        },
        "state": "CREATED",
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
            "history": {
                "stacktrace": None,
                "process_states": {
                    "CREATED": 1601303225.8234567,
                    "RUNNING": 1601303225.8702714
                }
            },
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
        "history": {
            "stacktrace": None,
            "process_states": {
                "CREATED": 1601303225.8234567,
                "RUNNING": 1601303225.8702714
            }
        },
        "state": "RUNNING",
        "uri": "http://localhost:5000/api/v1.0/procedures/1"
    }
}

STOP_PROCESS_RESPONSE = {
    "abort_message": "Successfully stopped script with ID 1"
}

STOP_PROCESS_AND_ABORT_SUBARRAY_ACTIVITY_RESPONSE = {
    "abort_message": "Successfully stopped script with ID 1 and aborted subarray activity"
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
        mock_server.put(f'{PROCEDURES_URI}/1', json=STOP_PROCESS_RESPONSE,
                        status_code=HTTPStatus.OK)

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.stop(procedure_id)

        last_request = mock_server.last_request

    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'state' in request_payload
    assert request_payload['abort'] is True
    assert request_payload['state'] == 'STOPPED'


def test_stop_procedure_sends_command_with_abort_true():
    """Check that the correct command is sent in the payload"""
    procedure_id = 1
    run_abort = True

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put(f'{PROCEDURES_URI}/1',
                        json=STOP_PROCESS_AND_ABORT_SUBARRAY_ACTIVITY_RESPONSE,
                        status_code=HTTPStatus.OK)

        adapter = RestAdapter(PROCEDURES_URI)
        adapter.stop(procedure_id, run_abort)

        last_request = mock_server.last_request

    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'state' in request_payload
    assert request_payload['abort'] is True
    assert request_payload['state'] == 'STOPPED'


# Additions by Liz Bartlett to test restclientUI maybe should be another file.

def test_restclientui_returns_error_when_not_passed_an_invalid_command():
    restclient = oet.procedure.application.restclient.__file__
    result = subprocess.run(['python3', restclient, 'blah'], capture_output=True, text=True)

    assert bool(result.stdout) is False
    assert result.stderr.count('ERROR') == 1


RESTUI_CREATE_RESPONSE = [
    ProcedureSummary(id=1, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                     script_uri='file:///app/scripts/allocate.py',
                     script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                  'run': {'args': [], 'kwargs': {}}},
                     history={'process_states': {'CREATED': 1603381492.3060987},
                              'stacktrace': None},
                     state='CREATED')]

RESTUI_LIST_RESPONSE = [
    [ProcedureSummary(id=1, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                      script_uri='file:///app/scripts/allocate.py',
                      script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                   'run': {'args': [], 'kwargs': {}}},
                      history={'process_states': {'CREATED': 1603378829.5842578},
                               'stacktrace': None},
                      state='CREATED'),
     ProcedureSummary(id=2, uri='http://127.0.0.1:5000/api/v1.0/procedures/2',
                      script_uri='file:///app/scripts/allocate.py',
                      script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                   'run': {'args': [], 'kwargs': {}}},
                      history={'process_states': {'CREATED': 1603379539.5662398},
                               'stacktrace': None},
                      state='CREATED')]
]

RESTUI_LIST_RESPONSE_WITH_STACKTRACE = [
    [ProcedureSummary(id=2, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                     script_uri='file:///app/scripts/allocate.py',
                     script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                  'run': {'args': [], 'kwargs': {}}},
                     history={'process_states': {'CREATED': 1603801915.4125392,
                                                 'FAILED': 1603801921.3564265,
                                                 'RUNNING': 1603801921.3464086},
                              'stacktrace': 'Traceback (most recent call last):\n  \
                              File "/app/oet/procedure/domain.py", line 132, in run\n    \
                              self.user_module.main(*args, **kwargs)\n  \
                              File "/app/scripts/allocate.py", line 47, in _main\n    \
                              allocated = subarray.allocate(allocation)\n  \
                              File "/app/oet/domain.py", line 363, in allocate\n    \
                              allocated = observingtasks.allocate_resources(self, resources)\n  \
                              File "/app/oet/observingtasks.py", line 352, in \
                              allocate_resources\n    command = \
                              get_allocate_resources_command(subarray, resources)\n  \
                              File "/app/oet/observingtasks.py", line 259, \
                              in get_allocate_resources_command\n    \
                              request = get_allocate_resources_request(subarray, resources, \
                              template_request)\n  \
                              File "/app/oet/observingtasks.py", \
                              line 228, in get_allocate_resources_request\n    \
                              template_sdp_config = template_request.sdp_config\n\
                              AttributeError: \'NoneType\' object has no \
                              attribute \'sdp_config\'\n'},
                     state='FAILED')]
]

RESTUI_START_RESPONSE = [
    ProcedureSummary(id=1, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                     script_uri='file:///app/scripts/allocate.py',
                     script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                  'run': {'args': [], 'kwargs': {}}},
                     history={'process_states': {'CREATED': 1603378829.5842578,
                                                 'RUNNING': 1603378900.5969338},
                              'stacktrace': None},
                     state='RUNNING')
]

RESTUI_LIST_RESPONSE_FOR_STOP_1 = [
    [ProcedureSummary(id=1, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                      script_uri='file:///app/scripts/test_working.py',
                      script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                   'run': {'args': [], 'kwargs': {}}},
                      history={'process_states': {'CREATED': 1603723668.9510045,
                                                  'RUNNING': 1603723677.0478802},
                               'stacktrace': None},
                      state='RUNNING')]
]

RESTUI_STOP_RESPONSE_1 = ['Successfully stopped script with ID 1 and aborted subarray activity']


RESTUI_LIST_RESPONSE_FOR_DESCRIBE_2 = [
    [ProcedureSummary(id=1, uri='http://127.0.0.1:5000/api/v1.0/procedures/1',
                      script_uri='file:///app/scripts/test_working.py',
                      script_args={'init': {'args': [], 'kwargs': {'subarray_id': 1}},
                                   'run': {'args': [], 'kwargs': {}}},
                      history={'process_states': {'COMPLETED': 1603723682.0246627,
                                                  'CREATED': 1603723668.9510045,
                                                  'RUNNING': 1603723677.0478802},
                               'stacktrace': None},
                      state='COMPLETED')
     ]
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
    for line in lines:
        elements = line.split()
        rest_response_object = {
            'id': elements[0],
            'uri': elements[1],
            'creation time': str(elements[2] + ' ' + elements[3]),
            'state': elements[4]}
        rest_responses.append(rest_response_object)
    return rest_responses


@mock.patch.object(RestAdapter, 'create')
def test_restclientui_creates_a_valid_script(mock_create_fn, capsys):
    mock_create_fn.side_effect = RESTUI_CREATE_RESPONSE
    fire.Fire(RestClientUI, ['create', 'file:///app/scripts/allocate.py'])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]['id'] == str(1)
    assert result[0]['uri'] == 'file:///app/scripts/allocate.py'
    assert result[0]['creation time'] == '2020-10-22 15:44:52'
    assert result[0]['state'] == 'CREATED'


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_lists_output(mock_list_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE
    fire.Fire(RestClientUI, ['list'])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]['id'] == str(1)
    assert result[1]['id'] == str(2)


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_start_output_when_nothing_to_start(mock_list_fn, capsys):
    mock_list_fn.side_effect = [[]]

    fire.Fire(RestClientUI, ['start'])
    captured = capsys.readouterr()

    assert 'No procedures to start' in captured.out


@mock.patch.object(RestAdapter, 'start')
@mock.patch.object(RestAdapter, 'list')
def test_restclientui_start_output_when_given_no_pid(mock_list_fn, mock_start_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE
    mock_start_fn.side_effect = RESTUI_START_RESPONSE

    fire.Fire(RestClientUI, ['start'])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]['state'] == 'RUNNING'
    mock_start_fn.assert_called_with(2, run_args=mock.ANY)


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_start_output_when_last_created_script_has_failed(mock_list_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE_WITH_STACKTRACE

    fire.Fire(RestClientUI, ['start'])
    captured = capsys.readouterr()

    assert 'The last procedure created is in FAILED state and cannot be started' in captured.out


@mock.patch.object(RestAdapter, 'start')
@mock.patch.object(RestAdapter, 'list')
def test_restclientui_start_output_when_given_pid(mock_list_fn, mock_start_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE
    mock_start_fn.side_effect = RESTUI_START_RESPONSE

    fire.Fire(RestClientUI, ['start', '--pid=1'])
    captured = capsys.readouterr()
    result = parse_rest_create_list_response(captured.out)

    assert result[0]['id'] == str(1)
    assert result[0]['state'] == 'RUNNING'
    mock_start_fn.assert_called_with(1, run_args=mock.ANY)


@mock.patch.object(RestAdapter, 'stop')
@mock.patch.object(RestAdapter, 'list')
def test_restclientui_stop_output_when_a_script_is_running(mock_list_fn, mock_stop_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE_FOR_STOP_1
    mock_stop_fn.side_effect = RESTUI_STOP_RESPONSE_1

    fire.Fire(RestClientUI, ['stop'])
    captured = capsys.readouterr()

    assert 'Successfully stopped script with ID 1 and aborted subarray activity' in captured.out
    mock_stop_fn.assert_called_with(1, True)


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_stop_output_when_a_script_is_not_running(mock_list_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE

    fire.Fire(RestClientUI, ['stop'])
    captured = capsys.readouterr()

    assert 'No procedures to stop' in captured.out


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_describe_when_stacktrace_present(mock_list_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE_WITH_STACKTRACE

    fire.Fire(RestClientUI, ['describe', '--pid=2'])
    captured = capsys.readouterr()
    lines = captured.out.split('\n')

    assert 'AttributeError' in captured.out
    assert 'FAILED' in lines[8]
    mock_list_fn.assert_called_with(2)


@mock.patch.object(RestAdapter, 'list')
def test_restclientui_describe_when_stacktrace_not_present(mock_list_fn, capsys):
    mock_list_fn.side_effect = RESTUI_LIST_RESPONSE_FOR_DESCRIBE_2

    fire.Fire(RestClientUI, ['describe', '--pid=1'])
    captured = capsys.readouterr()
    lines = captured.out.split('\n')

    assert 'COMPLETED' in lines[8]
    mock_list_fn.assert_called_with(1)

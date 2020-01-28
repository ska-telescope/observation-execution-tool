import requests_mock

from oet.procedure.application.restclient import RestClient

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

LIST_RESPONSE = {
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


def test_list_has_no_payload():
    """Ensure the payload for list does not exist"""
    with requests_mock.Mocker() as mock_server:
        mock_server.get('http://localhost:5000/api/v1.0/procedures',
                        json=LIST_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.list()

        last_request = mock_server.last_request

    # check that the request payload does not exist
    assert last_request.method == 'GET'
    assert last_request.text is None


def test_create_process_sends_expected_script_uri():
    """Check that the script uri is sent in the payload"""
    expected_uri = 'test_uri'

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post('http://localhost:5000/api/v1.0/procedures',
                         json=CREATE_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient(expected_uri)
        client.createProcess()

        last_request = mock_server.last_request

    request_payload = last_request.json()
    assert 'script_uri' in request_payload
    assert request_payload['script_uri'] == expected_uri


def test_create_process_sends_correct_script_args_when_user_doesnt_provide_arguments():
    """Check that default script args are sent"""
    expected_script_args = {
        'init': {
            'args': [],
            'kwargs': {}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post('http://localhost:5000/api/v1.0/procedures',
                         json=CREATE_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.createProcess()

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'POST'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args


def test_create_process_sends_correct_script_args_when_user_provides_arguments():
    """Check that user-supplied script arguments are sent"""
    expected_script_args = {
        'init': {
            'args': [3,6,9],
            'kwargs': {}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post('http://localhost:5000/api/v1.0/procedures',
                         json=CREATE_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.createProcess(init_args=expected_script_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'POST'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args


def test_start_execute_sends_correct_script_args_when_user_doesnt_provide_arguments():
    """Check that default script args are sent"""
    expected_script_args = {
        'run': {
            'args': [],
            'kwargs': {'scan_duration':14}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put('http://localhost:5000/api/v1.0/procedures/1',
                         json=START_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.createProcess()

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args


def test_start_execute_sends_correct_script_args_when_user_provides_arguments():
    """Check that user-supplied script arguments are sent"""
    expected_script_args = {
        'run': {
            'args': [5,10,15],
            'kwargs': {}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.put('http://localhost:5000/api/v1.0/procedures/1',
                         json=START_PROCESS_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.createProcess(init_args=expected_script_args)

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'PUT'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args

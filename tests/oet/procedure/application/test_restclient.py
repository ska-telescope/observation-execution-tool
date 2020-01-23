import requests_mock

from oet.procedure.application.restclient import RestClient

CREATE_SERVER_RESPONSE = {
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


def test_create_json_sends_expected_script_uri():
    expected_uri = 'test_uri'

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post('http://localhost:5000/api/v1.0/procedures',
                         json=CREATE_SERVER_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient(expected_uri)
        client.createProcess()

        last_request = mock_server.last_request

    request_payload = last_request.json()
    assert 'script_uri' in request_payload
    assert request_payload['script_uri'] == expected_uri


def test_create_json_sends_correct_script_args_when_user_doesnt_provide_arguments():
    expected_script_args = {
        'init': {
            'args': [],
            'kwargs': {}
        }
    }

    # create a mock requests object
    with requests_mock.Mocker() as mock_server:
        mock_server.post('http://localhost:5000/api/v1.0/procedures',
                         json=CREATE_SERVER_RESPONSE)

        # use the client to submit a CREATE request
        client = RestClient('script.py')
        client.createProcess()

        last_request = mock_server.last_request

    # check that the request JSON payload matches the expected values
    assert last_request.method == 'POST'
    request_payload = last_request.json()
    assert 'script_args' in request_payload
    assert request_payload['script_args'] == expected_script_args

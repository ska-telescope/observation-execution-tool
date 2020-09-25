"""
Unit tests for the procedure REST API module.
"""
import copy
import unittest.mock as mock
from http import HTTPStatus

import flask
import pytest

import oet.procedure.domain as domain
from oet.procedure.application import restserver
from oet.procedure.application.application import ProcedureSummary, PrepareProcessCommand, \
    StartProcessCommand, StopProcessCommand
from oet.procedure.domain import ProcedureInput

# Endpoint for the REST API
ENDPOINT = 'procedures'

# Valid JSON struct for creating a new procedure
CREATE_JSON = dict(script_uri="test:///test.py",
                   script_args={'init': dict(args=(1, 2, 3), kwargs=dict(kw1='a', kw2='b'))})

# object expected to be returned when creating the Procedure defined above
CREATE_SUMMARY = ProcedureSummary(
    id=1,
    script_uri='test:///test.py',
    script_args={'init': domain.ProcedureInput(1, 2, 3, kw1='a', kw2='b')},
    created_time= '2020-09-23T14:50:07',
    state=domain.ProcedureState.READY
)

ABORT_JSON = dict(state="STOP", abort=True)

# Valid JSON struct for starting a prepared procedure
RUN_JSON = dict(script_uri="test:///test.py",
                script_args={'run': dict(args=(4, 5, 6), kwargs=dict(kw3='c', kw4='d'))},
                created_time= '2020-09-23T14:50:07', state="RUNNING")

# object expected to be returned when the procedure is executed
RUN_SUMMARY = ProcedureSummary(
    id=1,
    script_uri='test:///test.py',
    script_args={'init': domain.ProcedureInput(1, 2, 3, kw1='a', kw2='b'),
                 'run': domain.ProcedureInput(4, 5, 6, kw3='c', kw4='d')},
    created_time= '2020-09-23T14:50:07',
    state=domain.ProcedureState.RUNNING
)

# resource partial URL for testing procedure execution with above JSON
RUN_ENDPOINT = f'{ENDPOINT}/{RUN_SUMMARY.id}'


def assert_json_equal_to_procedure_summary(summary: ProcedureSummary, summary_json: dict):
    """
    Helper function to compare JSON against a reference ProcedureSummary
    instance. An assertion error will be raised if the JSON does not match.

    :param summary: reference ProcedureSummary instance
    :param summary_json: JSON for the ProcedureSummmary
    """
    assert summary_json['uri'] == f'http://localhost/{ENDPOINT}/{summary.id}'
    assert summary_json['script_uri'] == summary.script_uri
    for method_name, arg_dict in summary_json['script_args'].items():
        i: ProcedureInput = summary.script_args[method_name]
        assert i.args == tuple(arg_dict['args'])
        assert i.kwargs == arg_dict['kwargs']
    assert summary_json['state'] == summary.state.name


@pytest.fixture
def client():
    """
    Test fixture that returns a Flask application instance
    """
    app = flask.Flask(__name__)
    app.register_blueprint(restserver.API, url_prefix='')
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_procedures_with_no_procedures_present_returns_empty_list(client):
    """
    Verify that listing resources returns an empty response when no procedures
    have been registered
    """
    response = client.get(ENDPOINT)
    response_json = response.get_json()
    assert 'procedures' in response_json
    assert response_json['procedures'] == []


def test_get_procedures_returns_expected_summaries(client):
    """
    Test that listing procedure resources returns the expected JSON payload
    """
    with mock.patch('oet.procedure.application.restserver.SERVICE.summarise',
                    return_value=[CREATE_SUMMARY]):
        response = client.get(ENDPOINT)
        assert response.status_code == 200
        response_json = response.get_json()
        assert 'procedures' in response_json
        procedures_json = response_json['procedures']
        assert len(procedures_json) == 1
        assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedures_json[0])


def test_get_procedure_by_id(client):
    """
    Verify that getting a resource by ID returns the expected JSON payload
    """
    with mock.patch('oet.procedure.application.restserver.SERVICE.summarise',
                    return_value=[CREATE_SUMMARY]):
        response = client.get(f'{ENDPOINT}/{CREATE_SUMMARY.id}')
        assert response.status_code == HTTPStatus.OK
        response_json = response.get_json()
        assert 'procedure' in response_json
        procedure_json = response_json['procedure']
        assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedure_json)


def test_get_procedure_gives_404_for_invalid_id(client):
    """
    Verify that requesting an invalid resource returns an error.
    """
    with mock.patch('oet.procedure.application.restserver.SERVICE.summarise') as mock_summarise:
        mock_summarise.side_effect = KeyError()
        response = client.get(f'{ENDPOINT}/1')
        assert response.status_code == HTTPStatus.NOT_FOUND


def test_successful_post_to_endpoint_returns_created_http_status(client):
    """
    Verify that creating a new Procedure returns the CREATED HTTP status code
    """
    response = client.post(ENDPOINT, json=CREATE_JSON)
    assert response.status_code == HTTPStatus.CREATED


def test_successful_post_to_endpoint_returns_summary_in_response(client):
    """
    Verify that creating a new Procedure returns the expected JSON payload:
    a summary of the created Procedure.
    """

    with mock.patch('oet.procedure.application.restserver.SERVICE.prepare') as mock_prepare:
        mock_prepare.return_value = CREATE_SUMMARY
        response = client.post(ENDPOINT, json=CREATE_JSON)
    response_json = response.get_json()
    assert 'procedure' in response_json
    procedure_json = response_json['procedure']
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, procedure_json)


def test_post_to_endpoint_requires_script_uri_json_parameter(client):
    """
    Verify that the script_uri must be present in the 'create procedure' JSON
    request.
    """
    malformed = copy.deepcopy(CREATE_JSON)
    del malformed['script_uri']
    response = client.post(ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_post_to_endpoint_requires_script_arg_be_a_dict(client):
    """
    Verify that the API checks the script_arg parameter is of the correct type
    """
    malformed = copy.deepcopy(CREATE_JSON)
    malformed['script_args'] = 'junk'
    response = client.post(ENDPOINT, json=malformed)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_post_to_endpoint_sends_init_arguments(client):
    """
    Verify that constructor arguments are passed through to the
    ScriptExecutionService when creating a new Procedure
    """
    expected = PrepareProcessCommand(script_uri=CREATE_SUMMARY.script_uri,
                                     init_args=CREATE_SUMMARY.script_args['init'])
    with mock.patch('oet.procedure.application.restserver.SERVICE.prepare') as mock_prepare:
        mock_prepare.return_value = CREATE_SUMMARY
        client.post(ENDPOINT, json=CREATE_JSON)
        mock_prepare.assert_called_once_with(expected)


def test_put_procedure_returns_404_if_procedure_not_found(client):
    """
    Verify that PUT to a missing Procedure returns 404 NoFound
    """
    with mock.patch('oet.procedure.application.restserver.SERVICE.summarise') as mock_summarise:
        mock_summarise.side_effect = KeyError()
        response = client.put(f'{ENDPOINT}/123')
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_put_procedure_returns_error_if_no_json_supplied(client):
    """
    Verify that a PUT request requires a JSON payload
    """
    with mock.patch('oet.procedure.application.restserver.SERVICE.summarise',
                    return_value=[CREATE_SUMMARY]):
        response = client.put(RUN_ENDPOINT)
    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_put_procedure_calls_run_on_execution_service(client):
    """
    Verify that the appropriate ScriptExecutionService methods are called
    when a valid 'start Procedure' PUT request is received
    """
    cmd = StartProcessCommand(process_uid=RUN_SUMMARY.id,
                              run_args=RUN_SUMMARY.script_args['run'])
    with mock.patch('oet.procedure.application.restserver.SERVICE') as mock_service:
        mock_service.summarise = mock.MagicMock(return_value=[CREATE_SUMMARY])
        mock_start = mock.MagicMock(return_value=RUN_SUMMARY)
        mock_service.start = mock_start

        response = client.put(RUN_ENDPOINT, json=RUN_JSON)
        mock_start.assert_called_once_with(cmd)
        response_json = response.get_json()
        assert 'procedure' in response_json
        assert_json_equal_to_procedure_summary(RUN_SUMMARY, response_json['procedure'])


def test_put_procedure_calls_stop_on_execution_service_and_executes_abort_script(client):
    """
    Verify that the appropriate ScriptExecutionService methods are called
    when a valid 'stop Procedure' PUT request is received
    """
    expected_response = 'Successfully stopped script with ID 1 and aborted subarray activity '
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id)

    with mock.patch('oet.procedure.application.restserver.SERVICE') as mock_service:
        mock_service.summarise.return_value = [RUN_SUMMARY]
        # list containing summary of abort process is returned when abort
        # script is running
        mock_service.stop.return_value = [RUN_SUMMARY]

        response = client.put(RUN_ENDPOINT, json=ABORT_JSON)
        response_json = response.get_json()

        mock_service.stop.assert_called_once_with(cmd, True)
        assert 'abort_message' in response_json
        assert response_json['abort_message'] == expected_response


def test_put_procedure_calls_stop_on_execution_service(client):
    """
    Verify that the appropriate ScriptExecutionService methods are called
    when a valid 'stop Procedure' PUT request is received
    """
    expected_response = 'Successfully stopped script with ID 1'
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id)

    with mock.patch('oet.procedure.application.restserver.SERVICE') as mock_service:
        mock_service.summarise.return_value = [RUN_SUMMARY]
        # empty list returned if post-termination process is not started
        mock_service.stop.return_value = []

        # PUT request should pick up default run_abort=True
        response = client.put(RUN_ENDPOINT, json=dict(state="STOP", abort=False))
        response_json = response.get_json()

        mock_service.stop.assert_called_once_with(cmd, False)
        assert 'abort_message' in response_json
        assert response_json['abort_message'] == expected_response


def test_put_procedure_does_not_start_a_procedure_unless_new_state_is_running(client):
    """
    Verify that the PUT is a no-op when the Procedure is already running
    """
    json = copy.deepcopy(RUN_JSON)
    del json['state']
    with mock.patch('oet.procedure.application.restserver.SERVICE') as mock_service:
        mock_service.summarise = mock.MagicMock(return_value=[CREATE_SUMMARY])
        mock_start = mock.MagicMock(return_value=RUN_SUMMARY)
        mock_service.start = mock_start

        _ = client.put(RUN_ENDPOINT, json=json)
        mock_start.assert_not_called()


def test_put_procedure_returns_procedure_summary(client):
    """
    Verify that PUT returns the expected JSON payload
    """
    json = copy.deepcopy(RUN_JSON)
    del json['state']
    with mock.patch('oet.procedure.application.restserver.SERVICE') as mock_service:
        mock_service.summarise = mock.MagicMock(return_value=[CREATE_SUMMARY])
        response = client.put(RUN_ENDPOINT, json=json)

    response_json = response.get_json()
    assert 'procedure' in response_json
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json['procedure'])

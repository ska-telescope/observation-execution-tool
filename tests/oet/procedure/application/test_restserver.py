"""
Unit tests for the procedure REST API module.
"""
import copy
from collections import OrderedDict
from http import HTTPStatus

import flask
import pytest
from pubsub import pub

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
    history=domain.ProcedureHistory(process_states=OrderedDict([(domain.ProcedureState.CREATED,
                                                                  1601295086.129294)]),
                                    stacktrace=None),
    state=domain.ProcedureState.CREATED
)

ABORT_JSON = dict(state="STOPPED", abort=True)

# Valid JSON struct for starting a prepared procedure
RUN_JSON = dict(script_uri="test:///test.py",
                script_args={'run': dict(args=(4, 5, 6), kwargs=dict(kw3='c', kw4='d'))},
                state="RUNNING")

# object expected to be returned when the procedure is executed
RUN_SUMMARY = ProcedureSummary(
    id=1,
    script_uri='test:///test.py',
    script_args={'init': domain.ProcedureInput(1, 2, 3, kw1='a', kw2='b'),
                 'run': domain.ProcedureInput(4, 5, 6, kw3='c', kw4='d')},
    history=domain.ProcedureHistory(process_states=OrderedDict([(domain.ProcedureState.CREATED,
                                                                  1601295086.129294),
                                                                 (domain.ProcedureState.RUNNING,
                                                                  1601295086.129294)]),
                                    stacktrace=None),
    state=domain.ProcedureState.RUNNING
)

# resource partial URL for testing procedure execution with above JSON
RUN_ENDPOINT = f'{ENDPOINT}/{RUN_SUMMARY.id}'


class PubSubHelper:
    def __init__(self, spec):
        messages = []
        self.messages = messages
        self.spec = spec
        pub.subscribe(self.respond, pub.ALL_TOPICS)

    def respond(self, topic=pub.AUTO_TOPIC, **msg_data):
        self.messages.append((topic, msg_data))

        if topic.name in self.spec:
            (args, kwargs) = self.spec[topic.name].pop()

            kwargs['msg_src'] = 'PubSubHelper'
            if 'request_id' in msg_data:
                kwargs['request_id'] = msg_data['request_id']
            pub.sendMessage(*args, **kwargs)

    @property
    def topics(self):
        topics = [topic.name for (topic, _) in self.messages]
        return topics

    def __getitem__(self, key):
        return self.messages[key]


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
    assert summary_json['history']['stacktrace'] == summary.history.stacktrace
    for key, val in summary.history.process_states.items():
        assert key.name in summary_json['history']['process_states']
        assert val == summary_json['history']['process_states'][key.name]
        assert isinstance(summary_json['history']['process_states'][key.name], float)


@pytest.fixture
def client():
    """
    Test fixture that returns a Flask application instance
    """
    app = flask.Flask(__name__)
    app.register_blueprint(restserver.API, url_prefix='')
    app.config['TESTING'] = True
    app.config['msg_src'] = 'unit tests'
    with app.test_client() as client:
        yield client


def test_get_procedures_with_no_procedures_present_returns_empty_list(client):
    """
    Verify that listing resources returns an empty response when no procedures
    have been registered
    """
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(ENDPOINT)
    response_json = response.get_json()
    assert 'procedures' in response_json
    assert response_json['procedures'] == []


def test_get_procedures_returns_expected_summaries(client):
    """
    Test that listing procedure resources returns the expected JSON payload
    """
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
    }
    _ = PubSubHelper(spec)

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
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
    }
    _ = PubSubHelper(spec)

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
    # empty list as response shows that PID not found when trying to retrieve
    # procedure
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[]))],
    }
    _ = PubSubHelper(spec)

    response = client.get(f'{ENDPOINT}/1')
    assert response.status_code == HTTPStatus.NOT_FOUND


def test_successful_post_to_endpoint_returns_created_http_status(client):
    """
    Verify that creating a new Procedure returns the CREATED HTTP status code
    """
    spec = {
        'request.script.create': [(['script.lifecycle.created'], dict(result=CREATE_SUMMARY))],
    }
    _ = PubSubHelper(spec)

    response = client.post(ENDPOINT, json=CREATE_JSON)
    assert response.status_code == HTTPStatus.CREATED


def test_successful_post_to_endpoint_returns_summary_in_response(client):
    """
    Verify that creating a new Procedure returns the expected JSON payload:
    a summary of the created Procedure.
    """
    spec = {
        'request.script.create': [(['script.lifecycle.created'], dict(result=CREATE_SUMMARY))],
    }
    _ = PubSubHelper(spec)

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
    Verify that constructor arguments are relayed correctly when creating a
    new Procedure.
    """
    spec = {
        'request.script.create': [(['script.lifecycle.created'], dict(result=CREATE_SUMMARY))],
    }
    helper = PubSubHelper(spec)

    client.post(ENDPOINT, json=CREATE_JSON)

    # verify message sequence and topics
    assert helper.topics == [
        'request.script.create',      # procedure creation requested
        'script.lifecycle.created',   # CREATED ProcedureSummary returned
    ]

    # now verify arguments were extracted from JSON and passed into command
    expected_cmd = PrepareProcessCommand(script_uri=CREATE_SUMMARY.script_uri,
                                         init_args=CREATE_SUMMARY.script_args['init'])
    assert helper.messages[0][1]['cmd'] == expected_cmd


def test_put_procedure_returns_404_if_procedure_not_found(client):
    """
    Verify that PUT to a missing Procedure returns 404 NotFound.
    """
    # empty list in response signifies that PID was not found when requesting
    # ProcedureSummary
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[]))],
    }
    helper = PubSubHelper(spec)

    response = client.put(f'{ENDPOINT}/123')
    assert response.status_code == HTTPStatus.NOT_FOUND

    # verify message sequence and topics
    assert helper.topics == [
        'request.script.list',      # procedure retrieval requested
        'script.pool.list',         # no procedure returned
    ]


def test_put_procedure_returns_error_if_no_json_supplied(client):
    """
    Verify that a PUT request requires a JSON payload
    """
    # The procedure is retrieved before the JSON is examined, hence we need to
    # prime the pubsub messages
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT)
    assert response.status_code == HTTPStatus.BAD_REQUEST

    # verify message sequence and topics
    assert helper.topics == [
        'request.script.list',      # procedure retrieval requested
        'script.pool.list',         # procedure returned
    ]


def test_put_procedure_calls_run_on_execution_service(client):
    """
    Verify that the appropriate ScriptExecutionService methods are called
    when a valid 'start Procedure' PUT request is received
    """
    # Message sequence for starting a CREATED procedure is:
    # 1. request.script.list to retrieve the Procedure to inspect
    # 2. script.pool.list is sent with response = [ProcedureSummary]
    # Code sees old state is CREATED, required state is RUNNING
    # 3. request.script.start is sent to request procedure starts execution
    # 4. script.lifecycle.started response sent with list containing
    #    ProcedureSummary describing procedure which is now running
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
        'request.script.start': [(['script.lifecycle.started'], dict(result=RUN_SUMMARY))],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=RUN_JSON)
    response_json = response.get_json()

    # verify RUNNING ProcedureSummary is contained in response JSON
    assert 'procedure' in response_json
    assert_json_equal_to_procedure_summary(RUN_SUMMARY, response_json['procedure'])

    # verify message sequence and topics
    assert helper.topics == [
        'request.script.list',      # procedure retrieval requested
        'script.pool.list',         # procedure returned
        'request.script.start',     # procedure abort requested
        'script.lifecycle.started'  # procedure abort response
    ]

    # verify correct procedure was started
    expected_cmd = StartProcessCommand(process_uid=RUN_SUMMARY.id, run_args=RUN_SUMMARY.script_args['run'])
    assert helper.messages[2][1]['cmd'] == expected_cmd


def test_put_procedure_calls_stop_and_executes_abort_script(client):
    """
    Verify that the correct messages are sent when a valid request to stop and
    abort a running procedure is received.
    """
    # Message sequence for stopping a RUNNING procedure is:
    # 1. request.script.list to retrieve the Procedure to inspect
    # 2. script.pool.list is sent with response = [ProcedureSummary]
    # Code sees old state is RUNNING, required state is STOPPED
    # 3. request.script.stop is sent to request script abort
    # 4. script.lifecycle.stopped response sent with list containing
    #    ProcedureSummary for abort script which is now running
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[RUN_SUMMARY]))],
        'request.script.stop': [(['script.lifecycle.stopped'], dict(result=[RUN_SUMMARY]))],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=ABORT_JSON)
    response_json = response.get_json()

    # verify message sequence and topics
    assert helper.topics == [
        'request.script.list',  # procedure retrieval requested
        'script.pool.list',  # procedure returned
        'request.script.stop',  # procedure abort requested
        'script.lifecycle.stopped'  # procedure abort response
    ]

    # verify command payload - correct procedure should be stopped in step #3
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id, run_abort=True)
    assert helper.messages[2][1]['cmd'] == cmd

    assert 'abort_message' in response_json
    expected_response = 'Successfully stopped script with ID 1 and aborted subarray activity '
    assert response_json['abort_message'] == expected_response


def test_put_procedure_calls_stop_on_execution_service(client):
    """
    Verify that the correct messages are sent when a valid PUT request to stop
    but not abort a running procedure is received.
     """
    # Message sequence for stopping a RUNNING procedure is:
    # 1. request.script.list to retrieve the Procedure to inspect
    # 2. script.pool.list is sent with response = [ProcedureSummary]
    # - code sees old state is RUNNING, required state is STOPPED
    # 3. request.script.stop is sent to request script abort
    # 4. script.lifecycle.stopped response sent with empty list, showing no
    #    abort script is running
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[RUN_SUMMARY]))],
        'request.script.stop': [(['script.lifecycle.stopped'], dict(result=[]))],
    }
    helper = PubSubHelper(spec)

    response = client.put(RUN_ENDPOINT, json=dict(state="STOPPED", abort=False))
    response_json = response.get_json()

    # verify message topic and order
    assert helper.topics == [
        'request.script.list',       # procedure retrieval requested
        'script.pool.list',          # procedure returned
        'request.script.stop',       # procedure abort requested
        'script.lifecycle.stopped'   # procedure abort response
    ]

    # correct procedure should be stopped
    cmd = StopProcessCommand(process_uid=RUN_SUMMARY.id, run_abort=False)
    assert helper.messages[2][1]['cmd'] == cmd

    assert 'abort_message' in response_json
    expected_response = 'Successfully stopped script with ID 1'
    assert response_json['abort_message'] == expected_response


def test_put_procedure_does_not_start_a_procedure_unless_new_state_is_running(client):
    """
    Verify that a PUT request does not start execution if the new state is not
    RUNNING.
    """
    # Message sequence is:
    # 1. request.script.list to retrieve the Procedure to inspect
    # 2. script.pool.list is sent with response = [ProcedureSummary]
    # - code sees new state is not RUNNING, realises it's a no-op request
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
    }
    helper = PubSubHelper(spec)

    # Deleting 'state' from JSON makes the PUT request a no-op (=no transition
    # required)
    json = copy.deepcopy(RUN_JSON)
    del json['state']
    _ = client.put(RUN_ENDPOINT, json=json)

    # assert that request to start a procedure was not broadcast
    assert 'request.script.start' not in helper.topics


def test_put_procedure_returns_procedure_summary(client):
    """
    Verify that PUT returns the expected JSON payload even if a state
    transition doesn't occur
    """
    # Message sequence is:
    # 1. request.script.list to retrieve the Procedure to inspect
    # 2. script.pool.list is sent with response = [ProcedureSummary]
    # - code sees new state is not RUNNING, realises it's a no-op request
    spec = {
        'request.script.list': [(['script.pool.list'], dict(result=[CREATE_SUMMARY]))],
    }
    helper = PubSubHelper(spec)

    # Deleting 'state' from JSON makes the operation a no-op (=no transition
    # required)
    json = copy.deepcopy(RUN_JSON)
    del json['state']

    response = client.put(RUN_ENDPOINT, json=json)
    response_json = response.get_json()

    assert 'procedure' in response_json
    assert_json_equal_to_procedure_summary(CREATE_SUMMARY, response_json['procedure'])

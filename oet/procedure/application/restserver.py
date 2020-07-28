"""
This module presents a REST interface to the script execution service.
"""
import flask

from . import application
from .. import domain

# Blueprint for the REST API
API = flask.Blueprint('api', __name__)

# The OET service made public by this API
SERVICE = application.ScriptExecutionService()


def _get_summary_or_404(pid):
    """
    Get a ProcedureSummary, raising a Flask 404 if not found.

    :param pid: ID of Procedure
    :return: ProcedureSummary
    """
    try:
        summaries = SERVICE.summarise([pid])
    except KeyError:
        flask.abort(404, description='Resource not found')
    else:
        return summaries[0]


@API.route('/procedures', methods=['GET'])
def get_procedures():
    """
    List all Procedures.

    This returns a list of Procedure JSON representations for all
    Procedures held by the service.

    :return: list of Procedure JSON representations
    """
    summaries = SERVICE.summarise()
    return flask.jsonify({'procedures': [make_public_summary(s) for s in summaries]})


@API.route('/procedures/<int:procedure_id>', methods=['GET'])
def get_procedure(procedure_id: int):
    """
    Get a Procedure.

    This returns the Procedure JSON representation of the requested
    Procedure.

    :param procedure_id: ID of the Procedure to return
    :return: Procedure JSON
    """
    summary = _get_summary_or_404(procedure_id)
    return flask.jsonify({'procedure': make_public_summary(summary)})


@API.route('/procedures', methods=['POST'])
def create_procedure():
    """
    Create a new Procedure.

    This method requests creation of a new Procedure as specified in the JSON
    payload POSTed to this function.

    :return: JSON summary of created Procedure
    """
    if not flask.request.json or not 'script_uri' in flask.request.json:
        flask.abort(400, description='script_uri missing')
    script_uri = flask.request.json['script_uri']

    if 'script_args' in flask.request.json and not isinstance(flask.request.json['script_args'],
                                                              dict):
        flask.abort(400, description='Malformed script_uri')
    script_args = flask.request.json.get('script_args', {})

    init_dict = script_args.get('init', {})
    init_args = init_dict.get('args', [])
    init_kwargs = init_dict.get('kwargs', {})

    procedure_input = domain.ProcedureInput(*init_args, **init_kwargs)
    prepare_cmd = application.PrepareProcessCommand(script_uri=script_uri,
                                                    init_args=procedure_input)
    summary = SERVICE.prepare(prepare_cmd)

    return flask.jsonify({'procedure': make_public_summary(summary)}), 201


@API.route('/procedures/<int:procedure_id>', methods=['PUT'])
def update_procedure(procedure_id: int):
    """
    Update a Procedure resource using the desired Procedure state described in
    the PUT JSON payload.

    :param procedure_id: ID of Procedure to modify
    :return: ProcedureSummary reflecting the final state of the Procedure
    """
    summary = _get_summary_or_404(procedure_id)

    if not flask.request.json:
        flask.abort(400)

    if 'script_args' in flask.request.json \
            and not isinstance(flask.request.json['script_args'], dict):
        flask.abort(400)
    script_args = flask.request.json.get('script_args', {})

    run_dict = script_args.get('run', {})
    run_args = run_dict.get('args', [])
    run_kwargs = run_dict.get('kwargs', {})
    procedure_input = domain.ProcedureInput(*run_args, **run_kwargs)

    old_state = summary.state
    new_state = domain.ProcedureState[flask.request.json.get('state', summary.state.name)]

    if old_state is domain.ProcedureState.RUNNING and new_state is domain.ProcedureState.STOP:
        cmd = application.StopProcessCommand(procedure_id)
        try:
            SERVICE.stop(cmd)
            msg = f'Successfully stopped script with ID {procedure_id} '
            return flask.jsonify({'abort_message': msg})
        except Exception as exc:
            flask.abort(500, exc)

    elif old_state is domain.ProcedureState.READY and new_state is domain.ProcedureState.RUNNING:
        cmd = application.StartProcessCommand(procedure_id, run_args=procedure_input)
        try:
            summary = SERVICE.start(cmd)
        except Exception as exc:
            flask.abort(500, exc)

    return flask.jsonify({'procedure': make_public_summary(summary)})


def make_public_summary(procedure: application.ProcedureSummary):
    """
    Convert a ProcedureSummary into JSON ready for client consumption.

    The main use of this function is to replace the internal Procedure ID with
    the resource URI, e.g., 1 -> http://localhost:5000/api/v1.0/procedures/1

    :param procedure: Procedure to convert
    :return: safe JSON representation
    """
    script_args = {method_name: {'args': method_args.args, 'kwargs': method_args.kwargs}
                   for method_name, method_args in procedure.script_args.items()}

    return {
        'uri': flask.url_for('api.get_procedure', procedure_id=procedure.id, _external=True),
        'script_uri': procedure.script_uri,
        'script_args': script_args,
        'state': procedure.state.name
    }


@API.errorhandler(404)
def resource_not_found(cause):
    """
    Custom 404 Not Found handler for Procedure API.

    :param cause: root exception for failure (e.g., KeyError)
    :return:
    """
    return flask.jsonify(error=str(cause)), 404


@API.errorhandler(400)
def bad_request(cause):
    """
    Custom 400 Bad Request handler for Procedure API.

    :param cause: root exception for failure (e.g., ValueError)
    :return:
    """
    return flask.jsonify(error=str(cause)), 400


@API.errorhandler(500)
def internal_server_error(cause):
    """
    Custom 404 Not Found handler for Procedure API.

    :param cause: root exception for failure (e.g., KeyError)
    :return:
    """
    return flask.jsonify(error=str(cause)), 500


def create_app(config_filename):
    """
    Create and return a new Flask app that will serve the REST API.

    :param config_filename:
    :return:
    """
    app = flask.Flask(__name__)
    # TODO get application config working
    # app.config.from_pyfile(config_filename)

    app.register_blueprint(API, url_prefix='/api/v1.0')
    return app

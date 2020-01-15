import flask

from . import application
from .. import domain

app = flask.Flask(__name__)
service = application.ScriptExecutionService()


def _get_summary_or_404(pid):
    try:
        summaries = service.summarise([pid])
    except KeyError:
        flask.abort(404, description='Resource not found')
    else:
        return summaries[0]


@app.route('/api/v1.0/procedures', methods=['GET'])
def get_procedures():
    summaries = service.summarise()
    return flask.jsonify({'procedures': [make_public_summary(s) for s in summaries]})


@app.route('/api/v1.0/procedures/<int:procedure_id>', methods=['GET'])
def get_procedure(procedure_id: int):
    summary = _get_summary_or_404(procedure_id)
    return flask.jsonify({'procedure': make_public_summary(summary)})


@app.route('/api/v1.0/procedures', methods=['POST'])
def create_procedure():
    if not flask.request.json or not 'script_uri' in flask.request.json:
        flask.abort(400, description='script_uri missing')
    script_uri = flask.request.json['script_uri']

    if 'script_args' in flask.request.json and not isinstance(flask.request.json, dict):
        flask.abort(400, description='Malformed script_uri')
    script_args = flask.request.json.get('script_args', {})

    init_dict = script_args.get('init', {})
    init_args = init_dict.get('args', [])
    init_kwargs = init_dict.get('kwargs', {})

    procedure_input = domain.ProcedureInput(*init_args, **init_kwargs)
    prepare_cmd = application.PrepareProcessCommand(script_uri=script_uri, init_args=procedure_input)
    summary = service.prepare(prepare_cmd)

    return flask.jsonify({'procedure': make_public_summary(summary)}), 201


@app.route('/api/v1.0/procedures/<int:procedure_id>', methods=['PUT'])
def update_procedure(procedure_id: int):
    summary = _get_summary_or_404(procedure_id)

    if not flask.request.json:
        flask.abort(400)

    # if 'run_args' in flask.request.json and not isinstance(flask.request.json['run_args'], list):
    #     flask.abort(400)
    # if 'running' in flask.request.json and type(flask.request.json['running']) is not bool:
    #     flask.abort(400)

    if 'script_args' in flask.request.json and not isinstance(flask.request.json, dict):
        flask.abort(400)
    script_args = flask.request.json.get('script_args', {})

    run_dict = script_args.get('run', {})
    run_args = run_dict.get('args', [])
    run_kwargs = run_dict.get('kwargs', {})
    procedure_input = domain.ProcedureInput(*run_args, **run_kwargs)

    # if 'state' in flask.request.json and not isinstance(flask.request.json, str):
    #     flask.abort(400)
    old_state = summary.state
    new_state = domain.ProcedureState[flask.request.json.get('state', summary.state.name)]
    if old_state is domain.ProcedureState.READY and new_state is domain.ProcedureState.RUNNING:
        cmd = application.StartProcessCommand(procedure_id, run_args=procedure_input)
        summary = service.start(cmd)

    return flask.jsonify({'procedure': make_public_summary(summary)})


def make_public_summary(procedure: application.ProcedureSummary):
    script_args = {method_name: {'args': method_args.args, 'kwargs': method_args.kwargs}
                   for method_name, method_args in procedure.script_args.items()}

    return {
        'uri': flask.url_for('get_procedure', procedure_id=procedure.id, _external=True),
        'script_uri': procedure.script_uri,
        'script_args': script_args,
        'state': procedure.state.name
    }


@app.errorhandler(404)
def resource_not_found(e):
    return flask.jsonify(error=str(e)), 404


@app.errorhandler(400)
def bad_request(e):
    return flask.jsonify(error=str(e)), 400


if __name__ == '__main__':
    app.run(debug=True)

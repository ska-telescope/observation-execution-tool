import time
from queue import Queue
from threading import Event

from flask import Flask, request, Response
from pubsub import pub

app = Flask(__name__)


def format_sse(data: str, event=None) -> str:
    msg = f'data: {data}\n\n'
    if event is not None:
        msg = f'event: {event}\n{msg}'
    return msg


@app.route('/stream', methods=['GET'])
def listen():
    def stream():
        q = Queue()
        def yieldit(*args, topic: pub.Topic=pub.AUTO_TOPIC, **kwargs):
            msg = format_sse(event=topic.name, data=f'args={args} kwargs={kwargs}')
            q.put(msg)
        pub.subscribe(yieldit, pub.ALL_TOPICS)

        while True:
            msg = q.get()
            yield msg

    return Response(stream(), mimetype='text/event-stream')


@app.route('/')
def hello_world():
    return 'Hello, World!'


@app.route('/create')
def create():
    """
    Simulate creation of a script. This function sends an event to mark the
    event in the UI domain - the user request - which triggers an action in
    the script execution domain, from which a reply event is published.

    This function is an experiment in turning an asynchronous sequence into
    a blocking call with a return value.
    """
    # setup a callback that will set an event when the 'script created' reply
    # event is received
    event = Event()
    request_id = time.time()
    status = {}

    def callback(*args, **kwargs):
        print(f'Callback arguments: {args} {kwargs}')
        # only match script creation events triggered by this request, as
        # signified by the matching request ID
        if kwargs['request_id'] == request_id:
            # This copies the status from the 'script created' event. In
            # production, this would copy the ProcedureSummary.
            status['status'] = kwargs['status']
            event.set()

    pub.subscribe(callback, 'script.lifecycle')

    # With the callback now setup, publish an event to mark the user request event
    pub.sendMessage('request.script.create', request_id=request_id)
    succeeded = event.wait(10)
    if succeeded:
        return f'Script created: {request_id}={status}'
    else:
        return 'Timed out'


@app.route('/seriouslykill', methods=['POST'])
def seriouslykill():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()
    return 'Stopping Flask'

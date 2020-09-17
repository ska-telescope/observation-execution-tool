import logging.config
import logging.handlers
import threading

import requests
from pubsub import pub

from mptools import (
    init_signals,
    default_signal_handler,
    MainContext,
    EventMessage,
    QueueProcWorker,
    web
)
from oet.procedure.application.application import (
    PrepareProcessCommand,
    StartProcessCommand,
    ScriptExecutionService
)


class EventBusWorker(QueueProcWorker):
    """
    EventBusWorker converts external inter-process pub/sub messages to and
    from local intra-process pubsub messages.

    EventBusWorker uses the QueueProcWorker's 'work queue' as an inbox for
    pub/sub EventMessages sent by other ProcWorkers. EventMessages received
    on this queue are rebroadcast locally as pypubsub messages. Likewise, the
    EventBusWorker listens to all pypubsub messages broadcast locally,
    converts them to pub/sub EventQueue messages, and puts them on the 'main'
    queue for transmission to other EventBusWorkers.
    """

    def republish(self, topic: pub.Topic = pub.AUTO_TOPIC, **kwargs) -> None:
        """
        Republish local event over inter-process event bus.

        :param topic: message topic, set automatically by pypubsub
        :param kwargs: any metadata associated with pypubsub message
        :return:
        """
        # avoid infinite loop - do not republish external events
        try:
            msg_src = kwargs.pop('msg_src')
        except KeyError:
            # No message source = virgin event published on pypubsub
            msg_src = self.name

        # ... but if this is a local message (message source = us), send it
        # out to the main queue and hence on to other EventBusWorkers
        if msg_src == self.name:
            # Convert pypubsub event to the equivalent mptools EventMessage
            msg = EventMessage(self.name, 'PUBSUB', dict(topic=topic.name, kwargs=kwargs))

            # not that this is a blocking put. If the queue is full, this call
            # will block until the queue has room to accept the message
            self.log(logging.DEBUG, 'Queueing internal event: %s', msg)
            self.event_q.put(msg)

    def startup(self) -> None:
        """
        Connect republishing function to pypubsub.
        """
        super().startup()
        # Request republish method be called for all pypubsub messages
        pub.subscribe(self.republish, pub.ALL_TOPICS)

    def shutdown(self) -> None:
        """
        Disconnect republishing function from pypubsub
        """
        super().shutdown()

        # Technically unsubscribing  is not necessary, as pypubsub holds weak
        # references to listeners and unsubscribes listeners that have been
        # deleted
        pub.unsubscribe(self.republish, pub.ALL_TOPICS)

    def main_func(self, evt: EventMessage) -> None:
        """
        Republish external pub/sub message locally.

        QueueProcWorker ensures that main_func is called for every item in the
        work queue. This function takes that work item - the external pub/sub
        EventMessage - and rebroadcasts it locally as a pypubsub message.

        :param evt: pub/sub EventMessage to broadcast locally
        """
        # avoid infinite loop - do not reprocess events that originated from us
        if evt.msg_src != self.name:
            self.log(logging.DEBUG, 'Republishing external event: %s', evt)
            payload = evt.msg
            topic = payload['topic']
            pub.sendMessage(topic, msg_src=evt.msg_src, **payload['kwargs'])
        else:
            self.log(logging.DEBUG, 'Discarding internal event: %s', evt)


class FlaskWorker(EventBusWorker):
    """
    FlaskWorker is an EventBusWorker that runs Flask.

    By extending EventBusWorker, Flask functions can use pypubsub to subscribe
    to and publish messages, and these messages will put on the main queue to
    be broadcast to other EventBusWorkers.
    """

    def startup(self) -> None:
        # Call super.startup to enable pypubsub <-> event queue republishing
        super().startup()

        # create app and start flask, using a thread as this is a blocking
        # call
        app = web.create_app(None)
        self.flask = threading.Thread(target=app.run, kwargs=dict(host='0.0.0.0'))
        self.flask.start()

    def shutdown(self) -> None:
        # Call super.shutdown to disconnect from pypubsub
        super().shutdown()

        # flask can only be shut down by accessing a special Werkzeug function
        # that is accessible from a request. Hence, we send a request to a
        # special URL that will access and call that function.
        requests.post('http://127.0.0.1:5000/api/v1.0/shutdown')
        self.flask.join(timeout=3)
        super().shutdown()


class ScriptExecutionServiceWorker(EventBusWorker):
    """
    ScriptExecutionService listens for user request messages, calling the
    appropriate ScriptExecutionService function and broadcasting its response.

    Actions that occur in the user request domain ('user clicked start
    observation', 'user aborted observation using the CLI', etc.) are
    broadcast as events. ScriptExecutionServiceWorker listens for events on
    these topics and triggers the required action in the script execution
    domain ('start a script', 'abort a script', etc.).

    Currently, the result of the action that occurred in the script execution
    domain (=the return object from the ScriptExecutionService) is broadcast
    to the world by the ScriptExectutionServiceWorker. This could change so
    that the ScriptExecutionService itself sends the message.
    """
    def prepare(self, msg_src, request_id: str, cmd: PrepareProcessCommand):
        self.log(logging.DEBUG, 'Prepare procedure request %s: %s', request_id, cmd)
        summary = self.ses.prepare(cmd)
        self.log(logging.DEBUG, 'Prepare procedure %s result: %s', request_id, summary)

        pub.sendMessage('script.lifecycle.created', request_id=request_id, result=summary)

    def start(self, msg_src, request_id: str, cmd: StartProcessCommand):
        self.log(logging.DEBUG, 'Start procedure request %s: %s', request_id, cmd)
        summary = self.ses.start(cmd)
        self.log(logging.DEBUG, 'Start procedure %s result: %s', request_id, summary)

        pub.sendMessage('script.lifecycle.started', request_id=request_id, result=summary)

    def list(self, msg_src, request_id: str, pids=None):
        self.log(logging.DEBUG, 'List procedures for request %s', request_id)
        summaries = self.ses.summarise(pids)
        self.log(logging.DEBUG, 'List result: %s', summaries)

        pub.sendMessage('script.pool.list', request_id=request_id, result=summaries)

    def startup(self) -> None:
        super().startup()

        self.ses = ScriptExecutionService()

        # wire up topics to the corresponding SES methods
        pub.subscribe(self.prepare, 'request.script.create')
        pub.subscribe(self.start, 'request.script.start')
        pub.subscribe(self.list, 'request.script.list')

    def shutdown(self) -> None:
        pub.unsubscribe(self.prepare, pub.ALL_TOPICS)
        pub.unsubscribe(self.start, pub.ALL_TOPICS)
        pub.unsubscribe(self.list, pub.ALL_TOPICS)
        super().shutdown()


def main(logging_config: dict):
    with MainContext() as main_ctx:
        main_ctx.init_logging(logging_config)

        init_signals(main_ctx.shutdown_event, default_signal_handler, default_signal_handler)

        manager_q = main_ctx.MPQueue()
        flask_q = main_ctx.MPQueue()
        event_bus_queues = [manager_q, flask_q]

        main_ctx.Proc("MANAGER", ScriptExecutionServiceWorker, manager_q)
        main_ctx.Proc("FLASK", FlaskWorker, flask_q)

        while not main_ctx.shutdown_event.is_set():
            event = main_ctx.event_queue.safe_get()
            if not event:
                continue
            elif event.msg_type == "PUBSUB":
                for q in event_bus_queues:
                    q.put(event)
            elif event.msg_type == "FATAL":
                main_ctx.log(logging.INFO, f"Fatal Event received: {event.msg}")
                break
            elif event.msg_type == "END":
                main_ctx.log(logging.INFO, f"Shutdown Event received: {event.msg}")
                break
            else:
                main_ctx.log(logging.ERROR, f"Unknown Event: {event}")


if __name__ == "__main__":
    logging_config = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': '%(asctime)s.%(msecs)03d %(source)-20s %(levelname)s %(message)s',
                'datefmt': '%H:%M:%S'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'verbose'
            },
            'werkzeug': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'simple'
            }
        },
        'loggers': {
            '': {
                'level': 'DEBUG',
                'handlers': ['console']
            },
            'werkzeug': {
                'level': 'ERROR',
                'handlers': ['werkzeug']
            }
        }
    }
    main(logging_config)

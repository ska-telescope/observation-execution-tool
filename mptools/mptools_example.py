import logging.config
import logging.handlers
import threading
import time

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


class EventBusWorker(QueueProcWorker):
    def republish(self, topic: pub.Topic = pub.AUTO_TOPIC, **kwargs) -> None:
        """
        Republish local event over interprocess event bus.

        :param topic: message topic, set automatically by pypubsub
        :param kwargs: any metadata associated with pypubsub message
        :return:
        """
        # avoid infinite loop - do not republish external events
        try:
            msg_src = kwargs.pop('msg_src')
        except KeyError:
            # No message source = a virgin event published on pypubsub
            msg_src = self.name

        if msg_src == self.name:
            # Convert pypubsub event to the equivalent mptools EventMessage
            msg = EventMessage(self.name, 'PUBSUB', dict(topic=topic.name, kwargs=kwargs))
            self.log(logging.DEBUG, 'Queueing internal event: %s', msg)
            self.event_q.put(msg)

    def startup(self) -> None:
        """
        Subscribes to all events published by pypubsub within this process,
        registered republish as the callback.
        """
        pub.subscribe(self.republish, pub.ALL_TOPICS)

    def shutdown(self) -> None:
        pub.unsubscribe(self.republish, pub.ALL_TOPICS)

    def main_func(self, evt: EventMessage):
        """
        Republish an external event within this processes' event bus.
        :param evt:
        :return:
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
    def startup(self) -> None:
        # Call super startup, so we have pypubsub <-> event queue republishing
        super().startup()
        # start flask, using a thread as this is a blocking call.
        self.flask = threading.Thread(target=web.app.run, kwargs=dict(host='0.0.0.0'))
        self.flask.start()

    def shutdown(self) -> None:
        super().shutdown()
        requests.post('http://localhost:5000/seriouslykill')
        self.flask.join()


class ScriptExecutionServiceWorker(EventBusWorker):
    def create(self, msg_src, request_id):
        """
        Function to simulate creation of a script.

        This function listens to UI request events, waits a few seconds to
        simulate processing, then publishes an event to say that the script was
        created.
        """
        def do_it():
            self.log(logging.DEBUG, 'Starting script for request %s', request_id)
            time.sleep(3)
            self.log(logging.DEBUG, 'Script complete for request %s', request_id)
            with self.lock:
                self.counter += 1
                status = f'Script {self.counter} created'
            pub.sendMessage('script.lifecycle.started', request_id=request_id, status=status)
            self.log(logging.DEBUG, 'Message published for request %s', request_id)

        t = threading.Thread(target=do_it)
        t.start()

    def startup(self):
        super().startup()

        self.counter = 0
        self.lock = threading.Lock()

        # this would wire up events to the corresponding SES methods
        pub.subscribe(self.create, 'request.script.create')

    def shutdown(self) -> None:
        pub.unsubscribe(self.republish, pub.ALL_TOPICS)
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

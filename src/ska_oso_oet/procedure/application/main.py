import logging.config
import logging.handlers
import threading
from typing import List

import requests
from flask import request
from pubsub import pub

from ska_oso_oet.event import topics
from ska_oso_oet.mptools import (
    EventMessage,
    MainContext,
    MPQueue,
    QueueProcWorker,
    default_signal_handler,
    init_signals,
)
from ska_oso_oet.procedure.application import restserver
from ska_oso_oet.procedure.application.application import (
    PrepareProcessCommand,
    ScriptExecutionService,
    StartProcessCommand,
    StopProcessCommand,
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
        Republish a local event over the inter-process event bus.

        :param topic: message topic, set automatically by pypubsub
        :param kwargs: any metadata associated with pypubsub message
        :return:
        """
        # avoid infinite loop - do not republish external events
        try:
            msg_src = kwargs.pop("msg_src")
        except KeyError:
            # No message source = virgin event published on pypubsub
            msg_src = self.name

        # ... but if this is a local message (message source = us), send it
        # out to the main queue and hence on to other EventBusWorkers
        if msg_src == self.name:
            # Convert pypubsub event to the equivalent mptools EventMessage
            msg = EventMessage(
                self.name, "PUBSUB", dict(topic=topic.name, kwargs=kwargs)
            )

            # not that this is a blocking put. If the queue is full, this call
            # will block until the queue has room to accept the message
            self.log(logging.DEBUG, "Queueing internal event: %s", msg)
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

        # Technically, unsubscribing is unnecessary as pypubsub holds weak
        # references to listeners and automatically unsubscribes listeners
        # that have been deleted
        pub.unsubscribe(self.republish, pub.ALL_TOPICS)

    # relax pylint to ignore renaming of item to evt. The base class handles
    # items of any type. We want to constrain this subclass to a more specific
    # event type.
    def main_func(self, evt: EventMessage) -> None:  # pylint: disable=arguments-renamed
        """
        Republish external pub/sub message locally.

        QueueProcWorker ensures that main_func is called for every item in the
        work queue. This function takes that work item - the external pub/sub
        EventMessage - and rebroadcasts it locally as a pypubsub message.

        :param evt: pub/sub EventMessage to broadcast locally
        """
        # avoid infinite loop - do not reprocess events that originated from us
        if evt.msg_src != self.name:
            self.log(logging.DEBUG, "Republishing external event: %s", evt)
            payload = evt.msg
            topic = payload["topic"]
            pub.sendMessage(topic, msg_src=evt.msg_src, **payload["kwargs"])
        else:
            self.log(logging.DEBUG, "Discarding internal event: %s", evt)

    def send_message(self, topic, **kwargs):
        pub.sendMessage(topic, msg_src=self.name, **kwargs)


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

        app = restserver.create_app()
        # add route to run shutdown_flask() when /shutdown is accessed
        app.add_url_rule("/shutdown", "shutdown", self.shutdown_flask, methods=["POST"])

        # override default msg_src with our real process name
        app.config.update(msg_src=self.name)

        # start Flask in a thread as app.run is a blocking call
        # self.flask can't be created in __init__ as we want this thread to belong to
        # the child process, not the spawning process
        self.flask = threading.Thread(  # pylint: disable=attribute-defined-outside-init
            target=app.run, kwargs=dict(host="0.0.0.0")
        )
        self.flask.start()

    def shutdown(self) -> None:
        # Call super.shutdown to disconnect from pypubsub
        super().shutdown()

        # flask can only be shut down by accessing a special Werkzeug function
        # that is accessible from a request. Hence, we send a request to a
        # special URL that will access and call that function.
        requests.post("http://127.0.0.1:5000/shutdown")
        self.flask.join(timeout=3)
        super().shutdown()

    @staticmethod
    def shutdown_flask():
        func = request.environ.get("werkzeug.server.shutdown")
        if func is None:
            raise RuntimeError("Not running with the Werkzeug Server")
        func()
        return "Stopping Flask"


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
    to the world by the ScriptExecutionServiceWorker. This could change so
    that the ScriptExecutionService itself sends the message.
    """

    def prepare(
        self,
        # msg_src MUST be part of method signature for pypubsub to function
        msg_src,  # pylint: disable=unused-argument
        request_id: str,
        cmd: PrepareProcessCommand,
    ):
        self.log(logging.DEBUG, "Prepare procedure request %s: %s", request_id, cmd)
        try:
            summary = self.ses.prepare(cmd)

        except Exception as e:
            self.log(logging.INFO, "Prepare procedure %s failed: %s", request_id, e)

            # TODO create failure topic for failures in procedure domain
            self.send_message(
                topics.procedure.lifecycle.created, request_id=request_id, result=e
            )

        else:
            self.log(
                logging.DEBUG, "Prepare procedure %s result: %s", request_id, summary
            )
            self.send_message(
                topics.procedure.lifecycle.created,
                request_id=request_id,
                result=summary,
            )

    def start(
        self,
        # msg_src MUST be part of method signature for pypubsub to function
        msg_src,  # pylint: disable=unused-argument
        request_id: str,
        cmd: StartProcessCommand,
    ):
        try:
            self.log(logging.DEBUG, "Start procedure request %s: %s", request_id, cmd)
            summary = self.ses.start(cmd)
        except Exception as e:
            self.log(logging.INFO, "Start procedure %s failed: %s", request_id, e)

            # TODO create failure topic for failures in procedure domain
            self.send_message(
                topics.procedure.lifecycle.started, request_id=request_id, result=e
            )
        else:
            self.log(logging.DEBUG, "Start procedure %s result: %s", request_id, summary)
            self.send_message(
                topics.procedure.lifecycle.started, request_id=request_id, result=summary
            )

    def list(
        self,
        # msg_src MUST be part of method signature for pypubsub to function
        msg_src,  # pylint: disable=unused-argument
        request_id: str,
        pids=None,
    ):
        self.log(logging.DEBUG, "List procedures for request %s", request_id)
        try:
            summaries = self.ses.summarise(pids)
        except ValueError:
            # ValueError raised when PID not found.
            summaries = []

        self.log(logging.DEBUG, "List result: %s", summaries)
        self.send_message(
            topics.procedure.pool.list, request_id=request_id, result=summaries
        )

    def stop(
        self,
        # msg_src MUST be part of method signature for pypubsub to function
        msg_src,  # pylint: disable=unused-argument
        request_id: str,
        cmd: StopProcessCommand,
    ):
        self.log(logging.DEBUG, "Stop procedure request %s: %s", request_id, cmd)
        try:
            summary = self.ses.stop(cmd)
        except FileNotFoundError as e:
            # FileNotFoundError raised when abort.py script not found
            self.log(logging.INFO, "Stop procedure %s failed: %s", request_id, e)

            # TODO create failure topic for failures in procedure domain
            #  (or refactor abortion script creation so that FileNotFound
            #  is caught only once in prepare)
            self.send_message(
                topics.procedure.lifecycle.stopped, request_id=request_id, result=e
            )
        else:
            self.log(logging.DEBUG, "Stop result: %s", summary)

            self.send_message(
                topics.procedure.lifecycle.stopped,
                request_id=request_id,
                result=summary,
            )

    def startup(self) -> None:
        super().startup()

        # self.ses can't be created in __init__ as we want the service to belong to
        # the child process, not the spawning process
        self.ses = (  # pylint: disable=attribute-defined-outside-init
            ScriptExecutionService()
        )

        # wire up topics to the corresponding SES methods
        pub.subscribe(self.prepare, topics.request.procedure.create)
        pub.subscribe(self.start, topics.request.procedure.start)
        pub.subscribe(self.list, topics.request.procedure.list)
        pub.subscribe(self.stop, topics.request.procedure.stop)

    def shutdown(self) -> None:
        pub.unsubscribe(self.prepare, pub.ALL_TOPICS)
        pub.unsubscribe(self.start, pub.ALL_TOPICS)
        pub.unsubscribe(self.list, pub.ALL_TOPICS)
        pub.unsubscribe(self.stop, pub.ALL_TOPICS)

        self.ses.shutdown()
        super().shutdown()


def main():
    """
    Create the OET components and start an event loop that dispatches messages
    between them.

    :param logging_config:
    """
    # All queues and processes are created via a MainContext so that they are
    # shared correctly and have consistent lifecycle management
    with MainContext() as main_ctx:
        # wire SIGINT and SIGTERM signal handlers to the shutdown_event Event
        # monitored by all processes, so that the processes know when
        # application termination has been requested.
        init_signals(
            main_ctx.shutdown_event, default_signal_handler, default_signal_handler
        )

        # create our message queues:
        # manager_q is the message queue for messages from the ScriptExecutionWorker
        # flask_q is the queue for messages intended for the FlaskWorker process
        script_executor_q = main_ctx.MPQueue()
        flask_q = main_ctx.MPQueue()

        # event bus messages received on the event_queue (the main queue that
        # child processes push to and which the while loop below listens to)
        # will be pushed onto the queues in this list
        event_bus_queues = [script_executor_q, flask_q]

        # create the OET components, which will run in child Python processes
        # and monitor the message queues here for event bus messages
        main_ctx.Proc("SESWorker", ScriptExecutionServiceWorker, script_executor_q)
        main_ctx.Proc("FlaskWorker", FlaskWorker, flask_q)

        # with all workers and queues set up, start processing messages
        main_loop(main_ctx, event_bus_queues)


def main_loop(main_ctx: MainContext, event_bus_queues: List[MPQueue]):
    """
    Main message parsing and routing loop, extracted from main() to increase
    testability.

    :param main_ctx:
    :param event_bus_queues:
    :return:
    """
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
    main()

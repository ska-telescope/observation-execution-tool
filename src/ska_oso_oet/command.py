"""
The command module contains code that encapsulates Tango device interactions
(commands, attribute read/writes, etc.) and provides the means to execute
them.
The OET decouples functions from Tango devices so that the commands can be
managed and executed by a proxy. This allows the proxy to execute commands
asynchronously while listening for interrupt signals, while to the caller
the execution appears synchronous.
"""
from __future__ import annotations

import atexit
import logging
import multiprocessing
import os
import queue
import threading
import weakref
from typing import Dict, Tuple

import tango
from ska_ser_skuid.client import SkuidClient

from . import FEATURES

LOGGER = logging.getLogger(__name__)


class Attribute:
    """
    An abstraction of a Tango attribute.
    """

    def __init__(self, device: str, name: str):
        """
        Create an Attribute instance.

        :param device: the FQDN of the target Tango device
        :param name: the name of the attribute to read
        """
        self.device = device
        self.name = name

    def __repr__(self):
        return "<Attribute({!r}, {!r})>".format(self.device, self.name)

    def __eq__(self, other):
        if not isinstance(other, Attribute):
            return False
        return self.device == other.device and self.name == other.name


class Command:
    """
    An abstraction of a Tango command.
    """

    def __init__(self, device: str, command_name: str, *args, **kwargs):
        """
        Create a Tango command.
        :param device: the FQDN of the target Tango device
        :param command_name: the name of the command to execute
        :param args: unnamed arguments to be passed to the command
        :param kwargs: keyword arguments to be passed to the command
        """
        self.device = device
        self.command_name = command_name
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        arg_str = ", ".join(["{!r}".format(o) for o in self.args])
        kwarg_str = ", ".join(
            ["{!s}={!r}".format(k, v) for k, v in self.kwargs.items()]
        )
        return "<Command({!r}, {!r}, {}, {})>".format(
            self.device, self.command_name, arg_str, kwarg_str
        )

    def __eq__(self, other):
        if not isinstance(other, Command):
            return False
        return (
            self.device == other.device
            and self.command_name == other.command_name
            and self.args == other.args
            and self.kwargs == other.kwargs
        )


class TangoDeviceProxyFactory:  # pylint: disable=too-few-public-methods
    """
    A call to create Tango DeviceProxy clients.
    This class exists to allow unit tests to override the factory with an
    implementation that returns mock DeviceProxy instances.
    """

    def __call__(self, device_name: str) -> tango.DeviceProxy:
        proxy = tango.DeviceProxy(device_name)
        proxy.set_timeout_millis(10000)
        return proxy


class TangoExecutor:  # pylint: disable=too-few-public-methods
    """
    TangoExecutor is the proxy between calling code and Tango devices. It
    accepts encapsulated Tango interactions and performs them on behalf of the
    calling code.
    """

    class SingleQueueEventStrategy:
        """
        SingleQueueEventStrategy encapsulates the event handling behaviour of
        the TangoExecutor from ~October 2021, when all events were added to a
        single queue and subscriptions were created and released after each
        attribute read operation.

        We hope to replace this with a more advanced implementation that
        allows subscriptions to multiple events.

        :param mgr: SubscriptionManager instance used to observe events
        """

        def __init__(self, mgr: SubscriptionManager):
            self._subscription_manager = mgr
            self._subscribed = False
            self._queue = queue.Queue()

        def subscribe_event(self, attr: Attribute) -> int:
            """
            Subscribe to change events published by a Tango attribute.

            This strategy only supports one active subscription at any time.
            An exception will be raised if a second subscription is attempted.

            This method returns a subscription identifier which should be
            supplied to a subsequent unsubscribe_event method.

            :param attr: attribute to subscribe to
            :return: subscription identifier
            """
            if self._subscribed:
                raise Exception("Multiple subscriptions not allowed: %s", attr)

            LOGGER.debug("Observing %s/%s", attr.device, attr.name)
            self._subscription_manager.register_observer(attr, self)
            return -1

        def unsubscribe_event(self, attr: Attribute, subscription_id: int) -> None:
            """
            Unsubscribe to change events published by a Tango attribute.

            This strategy only supports one active subscription at any time.
            An exception will be raised if a second subscription is attempted.

            :param attr: attribute to unsubscribe from
            :param subscription_id: subscription identifier
            """
            LOGGER.debug("Unobserving %s/%s", attr.device, attr.name)
            self._subscription_manager.unregister_observer(attr, self)
            self._drain()
            self._subscribed = False

        def _drain(self):
            """
            Drains all events from the queue, blocking until the queue is empty.
            """
            drained = False
            while not drained:
                try:
                    self._queue.get(block=False)
                except queue.Empty:
                    drained = True

        def read_event(self, attr: Attribute) -> tango.EventData:
            """
            Read an event from the queue.

            With a single subscription active at any one time, the attribute
            is ignored by this implementation but is expected to be required
            by strategy that support multiple attribute subscriptions.
            """
            return self._queue.get()  # TODO: 1. implement timeout functionality

        def notify(self, evt: tango.EventData):
            """
            This implements the SubscriptionManager EventObserver interface. Tango
            ChangeEvents republished by the SubscriptionManager are received via
            this method.

            Queue is thread-safe so we do not need to synchronise this method with
            read_event.
            """
            LOGGER.debug("Received event: %s", evt)
            self._queue.put(evt)

    def __init__(self, proxy_factory=TangoDeviceProxyFactory()):
        """
        Create a new TangoExecutor.

        :param proxy_factory: a function or object which, when called, returns
            an object that conforms to the PyTango DeviceProxy interface.
        """
        self._proxy_factory = proxy_factory

        # maps
        subscription_manager = SubscriptionManager(proxy_factory)
        self._evt_strategy = TangoExecutor.SingleQueueEventStrategy(
            subscription_manager
        )

        # maps device names to device proxies. These proxies are used for
        # command execution and polling reads. There is scope for these to be
        # unified with the proxies used for event management.
        # TODO modify TangoDeviceProxyFactory to cache proxies?
        self._device_proxies: Dict[str, tango.DeviceProxy] = {}

    def execute(self, command: Command, **kwargs):
        """
        Execute a Command on a Tango device.

        Additional kwargs to the DeviceProxy can be specified if required.

        :param command: the command to execute
        :return: the response, if any, returned by the Tango device
        """
        proxy = self._get_proxy(command.device)
        param = None
        if len(command.args) == 1:
            param = command.args[0]
        if len(command.args) > 1:
            param = command.args
        LOGGER.info("Executing command: %r", command)
        return proxy.command_inout(command.command_name, cmd_param=param, **kwargs)

    def read(self, attribute: Attribute):
        """
        Read an attribute on a Tango device.

        :param attribute: the attribute to read
        :return: the attribute value
        """
        proxy = self._get_proxy(attribute.device)
        LOGGER.debug("Reading attribute: %s/%s", attribute.device, attribute.name)
        response = getattr(proxy, attribute.name)
        return response

    def subscribe_event(self, attribute: Attribute):
        """
        Subscribe event on a Tango device.

        :param attribute: the attribute to subscribe to
        :return: subscription ID
        """
        return self._evt_strategy.subscribe_event(attribute)

    def read_event(self, attr: Attribute) -> tango.EventData:
        """
        Get an event for the specified attribute.
        """
        return self._evt_strategy.read_event(
            attr
        )  # TODO: 1. implement timeout functionality

    def unsubscribe_event(self, attribute: Attribute, event_id: int):
        """
        unsubscribe event on a Tango device.

        :param attribute: the attribute to unsubscribe
        :param event_id: event subscribe id
        :return:
        """
        self._evt_strategy.unsubscribe_event(attribute, event_id)

    def _get_proxy(self, device_name: str) -> tango.DeviceProxy:
        # It takes time to construct and connect a device proxy to the remote
        # device, so instances are cached

        if device_name not in self._device_proxies:
            proxy = self._proxy_factory(device_name)
            self._device_proxies[device_name] = proxy
        return self._device_proxies[device_name]


class LocalScanIdGenerator:  # pylint: disable=too-few-public-methods
    """
    LocalScanIdGenerator is an abstraction of a service that will generate scan
    IDs as unique integers. Expect scan UID generation to be a database
    operation or similar in the production implementation.
    """

    def __init__(self, start=1):
        self.backing = multiprocessing.Value("i", start)

    @property
    def value(self):
        with self.backing.get_lock():
            return self.backing.value

    def next(self):
        """
        Get the next scan ID.

        :return: integer scan ID
        """
        previous_scan_id = self.value
        with self.backing.get_lock():
            self.backing.value += 1
            return previous_scan_id


class RemoteScanIdGenerator:  # pylint: disable=too-few-public-methods
    """
    RemoteScanIdGenerator connects to the skuid service to retrieve IDs
    """

    def __init__(self, hostname):
        self.skuid_client = SkuidClient(hostname)
        self.backing = multiprocessing.Value("i", -1)

    @property
    def value(self):
        with self.backing.get_lock():
            # Default value, scan id's should be > 0
            if self.backing.value == -1:
                self.next()
            return self.backing.value

    def next(self):
        """
        Get the next scan ID.

        :return: integer scan ID
        """
        with self.backing.get_lock():
            self.backing.value = self.skuid_client.fetch_scan_id()
            return self.backing.value


# class EventObserver(Protocol):
#     def notify(self, evt: tango.EventData) -> None:
#         ...


class Callback:
    """
    Callback is an observable that distributes Tango events received by the
    callback instance to all observers registered at the moment of event
    reception.
    """

    def __init__(self):
        # observers should not be kept alive due to registration
        # self.observers: weakref.WeakSet[EventObserver] = weakref.WeakSet()
        self._observers = weakref.WeakSet()

        # Observer notification is likely to run on a different thread from
        # observer registration, hence the observers set is locked before any
        # operation.
        self._observers_lock = threading.Lock()

        # Tango (or SKA implementation?) emits an event containing the current
        # device value when subscribing to attribute change events. This is
        # confusing as it's not a change in a value, just a statement of the
        # initial value. This flag is set if the 'discard first event' feature
        # flag is set and the first event is discarded.
        self._first_event_discarded = False

    def register_observer(self, observer):
        """
        Register an EventObserver.

        Once registered, the observer will be notified of all Tango events
        received by this instance.

        :param observer: observer to register
        """
        with self._observers_lock:
            self._observers.add(observer)

    def unregister_observer(self, observer):
        """
        Unregister an EventObserver.

        Unsubscribed observers will not receive Tango events subsequently
        received by this instance.

        :param observer: observer to register
        """
        with self._observers_lock:
            self._observers.discard(observer)

    def notify_observers(self, evt: tango.EventData):
        """
        Distribute an event to all registered observers.

        :param evt: event to distribute
        """
        # take a snapshot of observers to give stable state to iterate over.
        # We iterate over a copy rather than notifying while holding the lock
        # as we do not know how observer event processing will take.
        if FEATURES.discard_first_event and not self._first_event_discarded:
            self._first_event_discarded = True
            LOGGER.debug("Discarding first event: %s", evt)
            return

        with self._observers_lock:
            observers_copy = set(self._observers)

        for o in observers_copy:
            o.notify(evt)

    def __call__(self, evt: tango.EventData):
        """
        Called by Tango DeviceProxy on event reception. Tango expects a
        function, hence we implement __call__ to provide a function-like
        interface.
        """
        self.notify_observers(evt)


class SubscriptionManager:
    def __init__(self, proxy_factory=TangoDeviceProxyFactory()):
        self._proxy_factory = proxy_factory
        self._proxies: Dict[str, tango.DeviceProxy] = {}
        self._callbacks: Dict[Tuple[str, str], Callback] = {}
        # maps (device name, device attribute) to event subscription ID
        self._subscription_ids: Dict[Tuple[str, str], int] = {}

        atexit.register(self._unsubscribe_all)

    # py3.8
    # def register_observer(self, attr: Attribute, observer: EventObserver):
    def register_observer(self, attr: Attribute, observer):
        # the observer must be registered before the subscription is
        # established to prevent a window where an event could be received but
        # not distributed
        callback = self._get_callback(attr)
        callback.register_observer(observer)
        self._subscribe(callback, attr)

    def _subscribe(self, callback, attr):
        k = (attr.device, attr.name)
        if k not in self._subscription_ids:
            proxy = self._get_proxy(attr.device)
            LOGGER.debug("Subscribing to %s/%s", attr.device, attr.name)
            sub_id = proxy.subscribe_event(
                attr.name, tango.EventType.CHANGE_EVENT, callback
            )
            self._subscription_ids[k] = sub_id

    # py3.8
    # def register_observer(self, attr: Attribute, observer: EventObserver):
    def unregister_observer(self, attr: Attribute, observer):
        callback = self._get_callback(attr)
        callback.unregister_observer(observer)

    def _get_proxy(self, device_name: str) -> tango.DeviceProxy:
        if device_name not in self._proxies:
            proxy = self._proxy_factory(device_name)
            self._proxies[device_name] = proxy
        return self._proxies[device_name]

    def _get_callback(self, attr: Attribute) -> Callback:
        k = (attr.device, attr.name)
        if k in self._callbacks:
            return self._callbacks[k]

        callback = Callback()
        self._callbacks[k] = callback
        return callback

    def _unsubscribe_all(self):
        for (device, attr), pid in self._subscription_ids.items():
            proxy = self._get_proxy(device)
            LOGGER.debug("Unsubscribing ID %s (%s/%s)", pid, device, attr)
            proxy.unsubscribe_event(pid)
        self._subscription_ids.clear()


# hold scan ID generator at the module level
if "SKUID_URL" in os.environ:
    # SKUID_URL should be in the format HOST:PORT
    SCAN_ID_GENERATOR = RemoteScanIdGenerator(os.environ["SKUID_URL"])
else:
    SCAN_ID_GENERATOR = LocalScanIdGenerator()

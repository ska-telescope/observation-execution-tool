"""
The command module contains code that encapsulates Tango device interactions
(commands, attribute read/writes, etc.) and provides the means to execute
them.
The OET decouples functions from Tango devices so that the commands can be
managed and executed by a proxy. This allows the proxy to execute commands
asynchronously while listening for interrupt signals, while to the caller
the execution appears synchronous.
"""
import logging
import os
import multiprocessing
from queue import Queue
from typing import Dict
import tango

from skuid.client import SkuidClient

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
        return '<Attribute({!r}, {!r})>'.format(self.device, self.name)

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
        arg_str = ', '.join(['{!r}'.format(o) for o in self.args])
        kwarg_str = ', '.join(['{!s}={!r}'.format(k, v)
                               for k, v in self.kwargs.items()])
        return '<Command({!r}, {!r}, {}, {})>'.format(
            self.device, self.command_name, arg_str, kwarg_str
        )

    def __eq__(self, other):
        if not isinstance(other, Command):
            return False
        return self.device == other.device and \
               self.command_name == other.command_name and \
               self.args == other.args and \
               self.kwargs == other.kwargs


class TangoDeviceProxyFactory:  # pylint: disable=too-few-public-methods
    """
    A call to create Tango DeviceProxy clients.
    This class exists to allow unit tests to override the factory with an
    implementation that returns mock DeviceProxy instances.
    """

    def __call__(self, device_name: str) -> tango.DeviceProxy:
        return tango.DeviceProxy(device_name)


class TangoExecutor:  # pylint: disable=too-few-public-methods
    """
    TangoExecutor is the proxy between calling code and Tango devices. It
    accepts encapsulated Tango interactions and performs them on behalf of the
    calling code.
    """

    def __init__(self, proxy_factory=TangoDeviceProxyFactory()):
        """
        Create a new TangoExecutor.

        :param proxy_factory: a function or object which, when called, returns
            an object that conforms to the PyTango DeviceProxy interface.
        """
        self._proxy_factory = proxy_factory

        self._device_proxies: Dict[str, tango.DeviceProxy] = {}

        # subscription
        self.queue = Queue(maxsize=0)

    def execute(self, command: Command):
        """
        Execute a Command on a Tango device.

        :param command: the command to execute
        :return: the response, if any, returned by the Tango device
        """
        proxy = self._get_proxy(command.device)
        param = None
        if len(command.args) == 1:
            param = command.args[0]
        if len(command.args) > 1:
            param = command.args
        LOGGER.info('Executing command: %r', command)
        return proxy.command_inout(command.command_name, cmd_param=param)

    def read(self, attribute: Attribute):
        """
        Read an attribute on a Tango device.

        :param attribute: the attribute to read
        :return: the attribute value
        """
        proxy = self._get_proxy(attribute.device)
        LOGGER.debug('Reading attribute: %s/%s', attribute.device, attribute.name)
        response = getattr(proxy, attribute.name)
        return response

    def subscribe_event(self, attribute: Attribute):
        """
        subscribe event on a Tango device.

        :param attribute: the attribute to subscribe
        :return: the subscribe id
        """

        proxy = self._get_proxy(attribute.device)
        LOGGER.debug("%s Subscribing to %s", attribute.device, attribute.name)
        event_id = proxy.subscribe_event(attribute.name,
                                         tango.EventType.CHANGE_EVENT,
                                         self.handle_state_change)
        LOGGER.debug("%s Subscribed to %s (event type: %s, event id: %d)", attribute.device,
                     attribute.name, tango.EventType.CHANGE_EVENT, event_id)
        return event_id

    def handle_state_change(self, event: tango.EventData):
        """
        callback method triggered when subscribe event called
        successfully

        :param event:
        :return:
        """
        LOGGER.debug(f"Event callback, type: {event.event}, error: {event.err}")
        self.queue.put(event)

    def read_event(self) -> tango.EventData:
        """
        Read an event from the queue

        :param :
        :return:
         """
        return self.queue.get()  # TODO: 1. implement timeout functionality

    def unsubscribe_event(self, attribute: Attribute, event_id: int):
        """
           unsubscribe event on a Tango device.

           :param event_id: event subscribe id
           :param attribute: the attribute to unsubscribe
           :return:
        """
        proxy = self._get_proxy(attribute.device)
        LOGGER.debug('Unsubscribe event: %s/%s', attribute.device, attribute.name)
        return proxy.unsubscribe_event(event_id)

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
        self.backing = multiprocessing.Value('i', start)

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
        self.backing = multiprocessing.Value('i', -1)

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


# hold scan ID generator at the module level
if 'SKUID_URL' in os.environ:
    # SKUID_URL should be in the format HOST:PORT
    SCAN_ID_GENERATOR = RemoteScanIdGenerator(os.environ['SKUID_URL'])
else:
    SCAN_ID_GENERATOR = LocalScanIdGenerator()

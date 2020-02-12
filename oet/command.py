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
import multiprocessing

import tango

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

        # ideally we'd add type hints but we're still on Python 3.5 at the time of writing
        # self.device_proxies: typing.Dict[str, DeviceProxy] = {}
        self._device_proxies = {}

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

    def _get_proxy(self, device_name: str) -> tango.DeviceProxy:
        # It takes time to construct and connect a device proxy to the remote
        # device, so instances are cached
        if device_name not in self._device_proxies:
            proxy = self._proxy_factory(device_name)
            self._device_proxies[device_name] = proxy
        return self._device_proxies[device_name]


class ScanIdGenerator:  # pylint: disable=too-few-public-methods
    """
    ScanIDGenerator is an abstraction of a service that will generate scan
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


# hold scan ID generator at the module level
SCAN_ID_GENERATOR = ScanIdGenerator()

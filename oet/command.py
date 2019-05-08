"""
The command module contains code that encapsulates Tango device interactions
(commands, attribute read/writes, etc.) and provides the means to execute
them.

The OET decouples functions from Tango devices so that the commands can be
managed and executed by a proxy. This allows the proxy to execute commands
asynchronously while listening for interrupt signals, while to the caller
the execution appears synchronous.
"""
import tango


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
        return proxy.command_inout(command.command_name, cmd_param=param)

    def _get_proxy(self, device_name: str) -> tango.DeviceProxy:
        # It takes time to construct and connect a device proxy to the remote
        # device, so instances are cached
        if device_name not in self._device_proxies:
            proxy = self._proxy_factory(device_name)
            self._device_proxies[device_name] = proxy
        return self._device_proxies[device_name]

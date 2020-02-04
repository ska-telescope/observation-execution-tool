"""
Unit tests for the oet.command module.
"""
from unittest.mock import patch, Mock

from oet.command import Attribute, Command, TangoExecutor, TangoDeviceProxyFactory, ScanIdGenerator


def test_attribute_repr():
    """
    Verify that the repr string for an Attribute is correctly formatted
    """
    attr = Attribute('device', 'name')
    assert repr(attr) == '<Attribute(\'device\', \'name\')>'


def test_attribute_eq():
    """
    Verify that Attributes pointing to the same Tango device attribute are
    considered equal.
    """
    attr1 = Attribute('device', 'read')
    attr2 = Attribute('device', 'read')
    assert attr1 == attr2


def test_attribute_noteq():
    """
    Verify that Attributes pointing to different device attributes are not
    equal
    """
    attr1 = Attribute('device', 'read')
    attr2 = Attribute('device', 'write')
    assert attr1 != attr2


def test_command_eq_for_non_attr_objects():
    """
    Verify that Attribute is not equal to non-Attribute objects.
    """
    assert Attribute('device', 'attribute name') != 1
    assert Command('device', 'attribute name') != object()


def test_tango_executor_calls_arg_attribute_correctly():
    """
    Check that the TangoExecutor correctly invokes device server attribute that
    require a scalar argument.
    """


def test_command_repr():
    """
    Verify that the repr string for a Command is correctly formatted.
    """
    cmd = Command('device', 'command name', 1, 'def', 3, kw1='abc')
    assert repr(cmd) == '<Command(\'device\', \'command name\', 1, \'def\', 3, kw1=\'abc\')>'


def test_command_eq():
    """
    Verify that Commands with equal targets, commands, and command arguments
    are considered equal.
    """
    cmd1 = Command('device', 'command name', 1, 'def', 3, kw1='abc', kw2='def')
    cmd2 = Command('device', 'command name', 1, 'def', 3, kw2='def', kw1='abc')
    assert cmd1 == cmd2


def test_command_eq_for_non_command_objects():
    """
    Verify that Command is not equal to non-Command objects.
    """
    assert Command('device', 'command name') != 1
    assert Command('device', 'command name') != object()


def test_tango_executor_creates_proxy_to_specified_device():
    """
    Check that the TangoExecutor creates a proxy to the device specified in
    the Command.
    """
    cmd = Command('device', 'command')

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=Mock()) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    mock_call.assert_called_once_with('device')


def test_tango_executor_only_creates_one_device_proxy_per_device():
    """
    Check that the TangoExecutor uses cached DeviceProxy.
    """
    cmd = Command('device', 'command')

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=Mock()) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)
        executor.execute(cmd)

    mock_call.assert_called_once_with('device')


def test_tango_executor_calls_single_arg_command_correctly():
    """
    Check that the TangoExecutor correctly invokes device server commands that
    require a scalar argument.
    """
    mock_device_proxy = Mock()
    cmd = Command('device', 'command', 1)

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=mock_device_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    # single-valued arg should be unpacked
    mock_device_proxy.command_inout.assert_called_once_with('command', cmd_param=1)


def test_tango_executor_calls_multi_arg_command_correctly():
    """
    Check that the TangoExecutor correctly invokes device server commands that
    accept multiple arguments.
    :return:
    """
    mock_proxy = Mock()
    cmd = Command('device', 'command', 1, 2, 3)

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=mock_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    mock_proxy.command_inout.assert_called_once_with('command', cmd_param=(1, 2, 3))


def test_tango_device_proxy_creates_device_proxy_to_named_device():
    """
    Confirm that the TangoDeviceProxyFactory creates a DeviceProxy using the
    device name given as an argument.
    """
    with patch('oet.command.tango') as mock_pytango:
        _ = TangoDeviceProxyFactory()('my device')
    mock_pytango.DeviceProxy.assert_called_once_with('my device')


def test_tango_read_creates_proxy_to_specified_device():
    """
    Check that the TangoExecutor creates a proxy to the device specified in
    the Attribute.
    """
    attr = Attribute('device', 'name')

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=Mock()) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.read(attr)

    mock_call.assert_called_once_with('device')


def test_tango_read_only_creates_one_device_proxy_per_device():
    """
    Check that the TangoExecutor uses cached DeviceProxy.
    """
    attr = Attribute('device', 'name')

    with patch.object(TangoDeviceProxyFactory, '__call__', return_value=Mock()) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.read(attr)

    mock_call.assert_called_once_with('device')


def test_scan_id_generator_increments_on_next():
    """
    Confirm that the scan ID generator increments by one each call.
    """
    generator = ScanIdGenerator(start=5)
    expected = [5, 6, 7, 8, 9]
    actual = [generator.next() for _ in range(5)]
    assert actual == expected


def test_scan_id_generator_does_not_increment_when_reading_value():
    """
    Confirm that the scan ID generator does not increment the scan ID when
    reading the current value.
    """
    generator = ScanIdGenerator(start=5)
    expected = [5, 5, 5, 5, 5]
    actual = [generator.value for _ in range(5)]
    assert actual == expected
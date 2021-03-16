"""
Unit tests for the oet.command module.
"""
import json
import multiprocessing
from unittest.mock import patch, Mock, MagicMock

import tango

from oet.command import (
    Attribute,
    Command,
    TangoExecutor,
    TangoDeviceProxyFactory,
    LocalScanIdGenerator,
    RemoteScanIdGenerator,
)


def test_attribute_repr():
    """
    Verify that the repr string for an Attribute is correctly formatted
    """
    attr = Attribute("device", "name")
    assert repr(attr) == "<Attribute('device', 'name')>"


def test_attribute_eq():
    """
    Verify that Attributes pointing to the same Tango device attribute are
    considered equal.
    """
    attr1 = Attribute("device", "read")
    attr2 = Attribute("device", "read")
    assert attr1 == attr2


def test_attribute_noteq():
    """
    Verify that Attributes pointing to different device attributes are not
    equal
    """
    attr1 = Attribute("device", "read")
    attr2 = Attribute("device", "write")
    assert attr1 != attr2


def test_command_eq_for_non_attr_objects():
    """
    Verify that Attribute is not equal to non-Attribute objects.
    """
    assert Attribute("device", "attribute name") != 1
    assert Command("device", "attribute name") != object()


def test_tango_executor_calls_arg_attribute_correctly():
    """
    Check that the TangoExecutor correctly invokes device server attribute that
    require a scalar argument.
    """


def test_command_repr():
    """
    Verify that the repr string for a Command is correctly formatted.
    """
    cmd = Command("device", "command name", 1, "def", 3, kw1="abc")
    assert repr(cmd) == "<Command('device', 'command name', 1, 'def', 3, kw1='abc')>"


def test_command_eq():
    """
    Verify that Commands with equal targets, commands, and command arguments
    are considered equal.
    """
    cmd1 = Command("device", "command name", 1, "def", 3, kw1="abc", kw2="def")
    cmd2 = Command("device", "command name", 1, "def", 3, kw2="def", kw1="abc")
    assert cmd1 == cmd2


def test_command_eq_for_non_command_objects():
    """
    Verify that Command is not equal to non-Command objects.
    """
    assert Command("device", "command name") != 1
    assert Command("device", "command name") != object()


def test_tango_executor_creates_proxy_to_specified_device():
    """
    Check that the TangoExecutor creates a proxy to the device specified in
    the Command.
    """
    cmd = Command("device", "command")

    with patch.object(
        TangoDeviceProxyFactory, "__call__", return_value=Mock()
    ) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    mock_call.assert_called_once_with("device")


def test_tango_executor_only_creates_one_device_proxy_per_device():
    """
    Check that the TangoExecutor uses cached DeviceProxy.
    """
    cmd = Command("device", "command")

    with patch.object(
        TangoDeviceProxyFactory, "__call__", return_value=Mock()
    ) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)
        executor.execute(cmd)

    mock_call.assert_called_once_with("device")


def test_tango_executor_calls_single_arg_command_correctly():
    """
    Check that the TangoExecutor correctly invokes device server commands that
    require a scalar argument.
    """
    mock_device_proxy = Mock()
    cmd = Command("device", "command", 1)

    with patch.object(
        TangoDeviceProxyFactory, "__call__", return_value=mock_device_proxy
    ):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    # single-valued arg should be unpacked
    mock_device_proxy.command_inout.assert_called_once_with("command", cmd_param=1)


def test_tango_executor_calls_multi_arg_command_correctly():
    """
    Check that the TangoExecutor correctly invokes device server commands that
    accept multiple arguments.
    :return:
    """
    mock_proxy = Mock()
    cmd = Command("device", "command", 1, 2, 3)

    with patch.object(TangoDeviceProxyFactory, "__call__", return_value=mock_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.execute(cmd)

    mock_proxy.command_inout.assert_called_once_with("command", cmd_param=(1, 2, 3))


def test_tango_executor_calls_subscribe_event_correctly():
    """
    Check that the TangoExecutor correctly invokes subscribe event.
    :return:
    """
    mock_proxy = Mock()
    attr = Attribute("device", "name")

    with patch.object(TangoDeviceProxyFactory, "__call__", return_value=mock_proxy):
        mock_proxy.subscribe_event.return_value = 12345
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        resonse = executor.subscribe_event(attr)
    mock_proxy.subscribe_event.assert_called_once()
    assert resonse == 12345


def test_tango_executor_calls_read_event_correctly_check_queue_is_empty():
    """
    Check that the TangoExecutor correctly invokes read event.
    :return:
    """
    mock_proxy = Mock()

    with patch.object(TangoDeviceProxyFactory, "__call__", return_value=mock_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        evt = mock_proxy.MagicMock(spec_set=tango.EventData)
        evt.attr_value = "resourcing"
        executor.handle_state_change(evt)
        result = executor.read_event()
    assert result.attr_value == "resourcing"
    assert executor.queue.empty()


def test_tango_executor_calls_subscribe_event_callback_correctly():
    """
    Check that the TangoExecutor correctly invokes subscribe event callback.
    :return:
    """
    mock_proxy = Mock()

    with patch.object(TangoDeviceProxyFactory, "__call__", return_value=mock_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        evt = mock_proxy.MagicMock(spec_set=tango.EventData)
        evt.attr_value = "resourcing"
        executor.handle_state_change(evt)
        result = executor.read_event()
    assert result.attr_value == "resourcing"
    assert executor.queue.empty()


def test_tango_executor_calls_unsubscribe_event_correctly():
    """
    Check that the TangoExecutor correctly invokes unsubscribe event.
    :return:
    """
    mock_proxy = Mock()
    attr = Attribute("device", "name")
    with patch.object(TangoDeviceProxyFactory, "__call__", return_value=mock_proxy):
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        mock_proxy.subscribe_event.return_value = 12345
        response = executor.subscribe_event(attr)
        executor.unsubscribe_event(attr, 12345)
    assert response == 12345
    mock_proxy.unsubscribe_event.assert_called_once_with(response)


def test_tango_device_proxy_creates_device_proxy_to_named_device():
    """
    Confirm that the TangoDeviceProxyFactory creates a DeviceProxy using the
    device name given as an argument.
    """
    with patch("oet.command.tango") as mock_pytango:
        _ = TangoDeviceProxyFactory()("my device")
    mock_pytango.DeviceProxy.assert_called_once_with("my device")


def test_tango_read_creates_proxy_to_specified_device():
    """
    Check that the TangoExecutor creates a proxy to the device specified in
    the Attribute.
    """
    attr = Attribute("device", "name")

    with patch.object(
        TangoDeviceProxyFactory, "__call__", return_value=Mock()
    ) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.read(attr)

    mock_call.assert_called_once_with("device")


def test_tango_read_only_creates_one_device_proxy_per_device():
    """
    Check that the TangoExecutor uses cached DeviceProxy.
    """
    attr = Attribute("device", "name")

    with patch.object(
        TangoDeviceProxyFactory, "__call__", return_value=Mock()
    ) as mock_call:
        executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
        executor.read(attr)

    mock_call.assert_called_once_with("device")


def test_local_scan_id_generator_increments_on_next():
    """
    Confirm that the scan ID generator increments by one each call.
    """
    generator = LocalScanIdGenerator(start=5)
    expected = [5, 6, 7, 8, 9]
    actual = [generator.next() for _ in range(5)]
    assert actual == expected


def test_local_scan_id_generator_does_not_increment_when_reading_value():
    """
    Confirm that the scan ID generator does not increment the scan ID when
    reading the current value.
    """
    generator = LocalScanIdGenerator(start=5)
    expected = [5, 5, 5, 5, 5]
    actual = [generator.value for _ in range(5)]
    assert actual == expected


def test_remote_scan_id_generator_increments_on_next():
    """
    Confirm that the scan ID generator increments by one each call.
    """
    generator = None
    with patch("skuid.client.requests.get") as mocked_req:
        res = MagicMock()
        res.json.side_effect = [
            json.dumps({"scan_id": 1}),
            json.dumps({"scan_id": 2}),
            json.dumps({"scan_id": 3}),
            json.dumps({"scan_id": 4}),
        ]
        mocked_req.return_value = res
        generator = RemoteScanIdGenerator("url:1234")

        expected = [1, 2, 3]
        actual = [generator.next() for _ in range(3)]
        assert actual == expected


def test_remote_scan_id_generator_does_not_increment_when_reading_value():
    """
    Confirm that the scan ID generator does not increment the scan ID when
    reading the current value.
    """
    generator = None
    with patch("skuid.client.requests.get") as mocked_req:
        res = MagicMock()
        res.json.side_effect = [
            json.dumps({"scan_id": 1}),
            json.dumps({"scan_id": 2}),
            json.dumps({"scan_id": 3}),
        ]
        mocked_req.return_value = res
        generator = RemoteScanIdGenerator("url:1234")

        expected = [1, 1, 1]
        actual = [generator.value for _ in range(3)]
        assert actual == expected


def test_remote_scan_id_call_order():
    """
    Confirm that either value or next can be called first
    """
    generator = None
    with patch("skuid.client.requests.get") as mocked_req:
        res = MagicMock()
        res.json.side_effect = [
            json.dumps({"scan_id": 1}),
            json.dumps({"scan_id": 2}),
            json.dumps({"scan_id": 3}),
        ]
        mocked_req.return_value = res
        generator = RemoteScanIdGenerator("url:1234")
        assert generator.value == 1

    generator = None
    with patch("skuid.client.requests.get") as mocked_req:
        res = MagicMock()
        res.json.side_effect = [
            json.dumps({"scan_id": 1}),
            json.dumps({"scan_id": 2}),
            json.dumps({"scan_id": 3}),
        ]
        mocked_req.return_value = res
        generator = RemoteScanIdGenerator("url:1234")
        assert generator.next() == 1


def test_remote_scan_id_set_backing():
    """
    class `oet.procedure.domain::Procedure` can set the scan id itself if it's
    provided with one.
    Checking to make sure it does update and fetches next afterwards.
    """
    generator = None
    with patch("skuid.client.requests.get") as mocked_req:
        res = MagicMock()
        res.json.side_effect = [
            json.dumps({"scan_id": 98}),
            json.dumps({"scan_id": 99}),
            json.dumps({"scan_id": 100}),
        ]
        mocked_req.return_value = res
        generator = RemoteScanIdGenerator("url:1234")
        generator.backing = multiprocessing.Value("i", 3)
        expected = [3, 3, 3]
        actual = [generator.value for _ in range(3)]
        assert actual == expected

        expected = [98, 99, 100]
        actual = [generator.next() for _ in range(3)]
        assert actual == expected

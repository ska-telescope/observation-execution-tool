"""
Unit tests for the oet.command module.
"""
import threading
from contextlib import contextmanager
import json
import multiprocessing
from unittest.mock import patch, Mock, MagicMock

import tango

from oet.command import (
    Attribute,
    Callback,
    Command,
    TangoExecutor,
    TangoDeviceProxyFactory,
    LocalScanIdGenerator,
    RemoteScanIdGenerator,
    SubscriptionManager
)


class TestAttribute:
    def test_repr(self):
        """
        Verify that the repr string for an Attribute is correctly formatted
        """
        attr = Attribute("device", "name")
        assert repr(attr) == "<Attribute('device', 'name')>"

    def test_eq(self):
        """
        Verify that Attributes pointing to the same Tango device attribute are
        considered equal.
        """
        attr1 = Attribute("device", "read")
        attr2 = Attribute("device", "read")
        assert attr1 == attr2

    def test_attribute_noteq(self):
        """
        Verify that Attributes pointing to different device attributes are not
        equal
        """
        attr1 = Attribute("device", "read")
        attr2 = Attribute("device", "write")
        assert attr1 != attr2

    def test_eq_for_non_attr_objects(self):
        """
        Verify that Attribute is not equal to non-Attribute objects.
        """
        assert Attribute("device", "attribute name") != 1
        assert Attribute("device", "attribute name") != object()


class TestCommand:
    def test_command_repr(self):
        """
        Verify that the repr string for a Command is correctly formatted.
        """
        cmd = Command("device", "command name", 1, "def", 3, kw1="abc")
        assert repr(cmd) == "<Command('device', 'command name', 1, 'def', 3, kw1='abc')>"

    def test_command_eq(self):
        """
        Verify that Commands with equal targets, commands, and command arguments
        are considered equal.
        """
        cmd1 = Command("device", "command name", 1, "def", 3, kw1="abc", kw2="def")
        cmd2 = Command("device", "command name", 1, "def", 3, kw2="def", kw1="abc")
        assert cmd1 == cmd2

    def test_command_eq_for_non_command_objects(self):
        """
        Verify that Command is not equal to non-Command objects.
        """
        assert Command("device", "command name") != 1
        assert Command("device", "command name") != object()


@contextmanager
def call_via_mocks():
    mock_proxy = Mock()
    # prime the fake subscription IDs returned by subscribe_event
    mock_proxy.subscribe_event.side_effect = range(100)

    with patch.object(
            TangoDeviceProxyFactory, "__call__", return_value=mock_proxy
    ) as mock_call:
        try:
            yield mock_call, mock_proxy
        finally:
            pass


class TestTangoExecutor:
    def test_executor_creates_proxy_to_correct_device(self):
        """
        Check that the TangoExecutor creates a proxy to the device specified in
        the Command.
        """
        cmd = Command("device", "command")

        with call_via_mocks() as (mock_call, _):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.execute(cmd)

        mock_call.assert_called_once_with("device")

    def test_only_one_device_proxy_per_device(self):
        """
        Check that the TangoExecutor uses cached DeviceProxy.
        """
        cmd = Command("device", "command")

        with call_via_mocks() as (mock_call, _):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.execute(cmd)
            executor.execute(cmd)

        mock_call.assert_called_once_with("device")

    def test_single_arg_commands_called_correctly(self):
        """
        Check that the TangoExecutor correctly invokes device server commands that
        require a scalar argument.
        """
        cmd = Command("device", "command", 1)

        with call_via_mocks() as (_, mock_proxy):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.execute(cmd)

        # single-valued arg should be unpacked
        mock_proxy.command_inout.assert_called_once_with("command", cmd_param=1)

    def test_multiple_arg_commands_called_correctly(self):
        """
        Check that the TangoExecutor correctly invokes device server commands that
        accept multiple arguments.
        :return:
        """
        cmd = Command("device", "command", 1, 2, 3)

        with call_via_mocks() as (_, mock_proxy):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.execute(cmd)

        mock_proxy.command_inout.assert_called_once_with("command", cmd_param=(1, 2, 3))

    def test_tango_executor_calls_subscribe_event_correctly(self):
        """
        Check that the TangoExecutor correctly invokes subscribe event.
        :return:
        """
        attr = Attribute("device", "name")

        with call_via_mocks() as (_, mock_proxy):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            response = executor.subscribe_event(attr)
        mock_proxy.subscribe_event.assert_called_once()
        assert response == -1

    def test_read_event_returns_event_from_callback(self):
        attr = Attribute("device", "name")
        expected_evt = Mock(spec=tango.EventData)

        # Tango calls the supplied callback on a new thread, supplying an
        # EventData as argument
        def fake_subscribe(_, __, cb):
            t = threading.Thread(target=cb, args=(expected_evt,))
            t.start()
            t.join()
            # fake event subscription ID
            return 1

        with call_via_mocks() as (_, mock_proxy):
            mock_proxy.subscribe_event.side_effect = fake_subscribe
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            _ = executor.subscribe_event(attr)
            received_evt = executor.read_event(attr)

        assert received_evt == expected_evt


    def test_unsubscribe_keeps_tango_subscription(self):
        """
        Check that the TangoExecutor.unsubscribe does not unsubscribe from Tango events.
        """
        attr = Attribute("device", "name")
        with call_via_mocks() as (_, mock_proxy):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            pid = executor.subscribe_event(attr)
            executor.unsubscribe_event(attr, pid)
        assert not mock_proxy.unsubscribe_event.called

    def test_read_creates_proxy_to_specified_device(self):
        """
        Check that the TangoExecutor creates a proxy to the device specified in
        the Attribute.
        """
        attr = Attribute("device", "name")

        with call_via_mocks() as (mock_call, mock_proxy):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.read(attr)

        mock_call.assert_called_once_with("device")

    def test_read_uses_cached_deviceproxy(self):
        """
        Check that the TangoExecutor uses cached DeviceProxy.
        """
        attr = Attribute("device", "name")

        with call_via_mocks() as (mock_call, _):
            executor = TangoExecutor(proxy_factory=TangoDeviceProxyFactory())
            executor.read(attr)
            executor.read(attr)

        mock_call.assert_called_once_with("device")


def test_tango_device_proxy_creates_device_proxy_to_named_device():
    """
    Confirm that the TangoDeviceProxyFactory creates a DeviceProxy using the
    device name given as an argument.
    """
    with patch("oet.command.tango") as mock_pytango:
        _ = TangoDeviceProxyFactory()("my device")
    mock_pytango.DeviceProxy.assert_called_once_with("my device")


class TestLocalScanIdGenerator:
    def test_id_increments_on_next(self):
        """
        Confirm that the scan ID generator increments by one each call.
        """
        generator = LocalScanIdGenerator(start=5)
        expected = [5, 6, 7, 8, 9]
        actual = [generator.next() for _ in range(5)]
        assert actual == expected

    def test_id_does_not_increment_when_reading_value(self):
        """
        Confirm that the scan ID generator does not increment the scan ID when
        reading the current value.
        """
        generator = LocalScanIdGenerator(start=5)
        expected = [5, 5, 5, 5, 5]
        actual = [generator.value for _ in range(5)]
        assert actual == expected


class TestRemoteScanIdGenerator:
    def test_increments_on_next(self):
        """
        Confirm that the scan ID generator increments by one each call.
        """
        generator = None
        with patch("ska_ser_skuid.client.requests.get") as mocked_req:
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

    def test_id_does_not_increment_when_reading_value(self):
        """
        Confirm that the scan ID generator does not increment the scan ID when
        reading the current value.
        """
        generator = None
        with patch("ska_ser_skuid.client.requests.get") as mocked_req:
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

    def test_call_order(self):
        """
        Confirm that either value or next can be called first
        """
        generator = None
        with patch("ska_ser_skuid.client.requests.get") as mocked_req:
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
        with patch("ska_ser_skuid.client.requests.get") as mocked_req:
            res = MagicMock()
            res.json.side_effect = [
                json.dumps({"scan_id": 1}),
                json.dumps({"scan_id": 2}),
                json.dumps({"scan_id": 3}),
            ]
            mocked_req.return_value = res
            generator = RemoteScanIdGenerator("url:1234")
            assert generator.next() == 1

    def test_set_backing(self):
        """
        class `oet.procedure.domain::Procedure` can set the scan id itself if it's
        provided with one.
        Checking to make sure it does update and fetches next afterwards.
        """
        with patch("ska_ser_skuid.client.requests.get") as mocked_req:
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


class TestSubscriptionManager:
    def test_device_proxy_is_created_for_initial_observer(self):
        attr = Attribute('device', 'attribute')
        with call_via_mocks() as (mock_call, _):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            mgr.register_observer(attr, Mock())

        mock_call.assert_called_once_with("device")

    # def test_event_subscription_is_created_to_correct_device(self):

    def test_existing_device_proxy_is_reused_for_subsequent_observers(self):
        with call_via_mocks() as (mock_call, _):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            for i in range(10):
                attr = Attribute('device', 'attribute')
                mgr.register_observer(attr, Mock())

        mock_call.assert_called_once_with("device")

    def test_register_observer_adds_observer_to_appropriate_callback(self):
        attr = Attribute('device', 'attribute')
        observer = Mock()

        with call_via_mocks() as (mock_call, _):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            mgr.register_observer(attr, observer)
            assert observer in mgr._get_callback(attr)._observers

    def test_unregister_observer_removes_observer_from_appropriate_callback(self):
        attr = Attribute('device', 'attribute')
        observer = Mock()

        with call_via_mocks() as (mock_call, _):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            mgr.register_observer(attr, observer)
            mgr.unregister_observer(attr, observer)
            assert observer not in mgr._get_callback(attr)._observers

    def test_unsubscribe_all_releases_all_subscriptions(self):
        with call_via_mocks() as (mock_call, mock_proxy):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            for i in range(10):
                attr = Attribute('device', f'attr{i}')
                mgr.register_observer(attr, Mock())
            mgr._unsubscribe_all()

        for i in range(10):
            mock_proxy.unsubscribe_event.assert_any_call(i)

    def test_unregistering_does_not_create_a_new_subscription(self):
        attr = Attribute('device', 'attribute')
        observer = Mock()

        with call_via_mocks() as (mock_call, _):
            mgr = SubscriptionManager(proxy_factory=TangoDeviceProxyFactory())
            mgr.unregister_observer(attr, observer)

        assert not mock_call.called



class TestCallback:
    def test_all_observers_are_notified_of_received_events(self):
        cb = Callback()

        observers = [Mock() for _ in range(5)]
        for o in observers:
            cb.register_observer(o)

        mock_event = Mock(spec=tango.EventData)
        cb(mock_event)

        for o in observers:
            o.notify.assert_called_once_with(mock_event)

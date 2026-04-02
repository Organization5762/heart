"""Validate stream-driven output devices so outbound integrations share one transport shape."""

from __future__ import annotations

import threading

import pytest
import reactivex

from heart.device.flowtoy import FlowToyBridgeClient, FlowToyBridgeOutputDevice
from heart.device.output import OutputDevice, OutputMessage
from heart.peripheral.radio import FlowToyPattern, RadioDriver


class DummyDriver(RadioDriver):
    """Capture outbound radio commands so output-device serialization stays observable in tests."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def packets(self):  # pragma: no cover - unused for output tests
        yield from ()

    def send_raw_command(self, command: str) -> None:
        self.commands.append(command)

    def close(self) -> None:
        return None


class CollectingOutputDevice(OutputDevice):
    """Record emitted messages so stream binding behavior can be asserted precisely."""

    def __init__(self) -> None:
        self.messages: list[OutputMessage] = []
        self.event = threading.Event()

    def emit(self, message: OutputMessage) -> None:
        self.messages.append(message)
        self.event.set()


class TestFlowToyBridgeOutputDevice:
    """Cover FlowToy bridge serialization so writeback matches the discovered bridge command grammar."""

    @pytest.mark.parametrize(
        ("message", "expected_command"),
        [
            (OutputMessage.flowtoy_sync(1.5), "s1.5"),
            (OutputMessage.flowtoy_stop_sync(), "S"),
            (OutputMessage.flowtoy_reset_sync(), "a"),
            (
                OutputMessage.flowtoy_wake(group_id=3, group_is_public=True),
                "W3",
            ),
            (
                OutputMessage.flowtoy_power_off(group_id=4, group_is_public=False),
                "z4",
            ),
            (OutputMessage.flowtoy_raw_command("gshow,2"), "gshow,2"),
            (
                OutputMessage.flowtoy_pattern(
                    FlowToyPattern(
                        group_id=4,
                        group_is_public=True,
                        page=2,
                        mode=7,
                        actives=62,
                        hue_offset=120,
                        saturation=200,
                        brightness=180,
                        speed=90,
                        density=60,
                    )
                ),
                "P4,2,7,62,120,200,180,90,60,0,0,0,0",
            ),
            (
                OutputMessage.flowtoy_set_wifi(ssid="studio", password="secret"),
                "nstudio,secret",
            ),
            (
                OutputMessage.flowtoy_set_global_config(key="show", value=1),
                "gshow,1",
            ),
        ],
    )
    def test_emit_serializes_bridge_commands(
        self,
        message: OutputMessage,
        expected_command: str,
    ) -> None:
        """Verify each typed FlowToy output becomes the expected bridge command so future stream producers can target the radio bridge safely."""
        driver = DummyDriver()
        device = FlowToyBridgeOutputDevice(driver=driver)

        device.emit(message)

        assert driver.commands == [expected_command]

    def test_emit_rejects_non_flowtoy_messages(self) -> None:
        """Ensure FlowToy devices reject unrelated message kinds so stream wiring failures surface immediately instead of sending garbage to hardware."""
        driver = DummyDriver()
        device = FlowToyBridgeOutputDevice(driver=driver)

        with pytest.raises(ValueError):
            device.emit(OutputMessage.frame(b"not-a-radio-command"))


class TestOutputDeviceBinding:
    """Validate output-stream binding so reactive producers can feed devices without bespoke glue per transport."""

    def test_bind_forwards_stream_messages(self) -> None:
        """Verify binding drains observable messages into the device so output transports can be driven from asynchronous streams consistently."""
        device = CollectingOutputDevice()
        message = OutputMessage.flowtoy_stop_sync()

        subscription = device.bind(reactivex.just(message))
        try:
            assert device.event.wait(timeout=1.0) is True
        finally:
            subscription.dispose()

        assert device.messages == [message]


class TestFlowToyBridgeClient:
    """Validate the bridge client verbs so serial writeback has one canonical command encoder."""

    def test_client_exposes_bridge_verbs(self) -> None:
        """Verify the client serializes the full Heart-facing bridge command surface so peripherals and future stream senders stay aligned."""
        driver = DummyDriver()
        client = FlowToyBridgeClient(driver=driver)

        client.sync(timeout_seconds=2.0)
        client.stop_sync()
        client.reset_sync()
        client.wake(group_id=1, group_is_public=False)
        client.power_off(group_id=2, group_is_public=True)
        client.set_pattern(
            FlowToyPattern(group_id=3, group_is_public=False, page=1, mode=4)
        )
        client.set_wifi(ssid="studio", password="secret")
        client.set_global_config(key="show", value=2)

        assert driver.commands == [
            "s2",
            "S",
            "a",
            "w1",
            "Z2",
            "p3,1,4,0,0,0,0,0,0,0,0,0,0",
            "nstudio,secret",
            "gshow,2",
        ]

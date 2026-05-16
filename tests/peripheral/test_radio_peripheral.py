from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from manyfold import Graph
from manyfold.sensor_io import BackoffPolicy, RetryPolicy

from heart.peripheral.core import Input, PeripheralMessageEnvelope
from heart.peripheral.input_payloads import RadioPacket
from heart.peripheral.radio import (FLOWTOY_PATTERN_EVENT,
                                    FLOWTOY_RAW_COMMAND_EVENT,
                                    FLOWTOY_RESET_SYNC_EVENT,
                                    FLOWTOY_STOP_SYNC_EVENT,
                                    FLOWTOY_SYNC_EVENT, FLOWTOY_WAKE_EVENT,
                                    FlowToyPattern, RadioDriver,
                                    RadioPeripheral, RawRadioPacket,
                                    SerialRadioDriver, radio_detection_route,
                                    radio_error_route,
                                    radio_packet_event_route)


class DummyDriver(RadioDriver):
    """Track packets and commands so radio peripheral tests stay deterministic."""

    def __init__(self, packets: Iterator[RawRadioPacket] | None = None) -> None:
        self._packets = list(packets or [])
        self.closed = False
        self.commands: list[str] = []

    def packets(self) -> Iterator[RawRadioPacket]:
        yield from self._packets

    def send_raw_command(self, command: str) -> None:
        self.commands.append(command)

    def close(self) -> None:
        self.closed = True


class FailingDriver(RadioDriver):
    """Raise from packet iteration so graph node error routes can be tested."""

    def packets(self) -> Iterator[RawRadioPacket]:
        raise RuntimeError("radio unavailable")
        yield RawRadioPacket()

    def send_raw_command(self, command: str) -> None:
        raise AssertionError(f"unexpected command: {command}")


class FakeSerialHandle:
    """Capture serial writes so driver tests can validate bridge framing."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []
        self.closed = False
        self.flushed = False
        self.lines: list[bytes] = []
        self.reset_calls = 0

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def flush(self) -> None:
        self.flushed = True

    def readline(self) -> bytes:
        if not self.lines:
            return b""
        return self.lines.pop(0)

    def reset_input_buffer(self) -> None:
        self.reset_calls += 1

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "FakeSerialHandle":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class FakeSerialModule:
    """Construct fake handles so SerialRadioDriver tests avoid host serial ports."""

    def __init__(self) -> None:
        self.handles: list[FakeSerialHandle] = []

    def Serial(self, *_args: Any, **_kwargs: Any) -> FakeSerialHandle:
        handle = FakeSerialHandle()
        self.handles.append(handle)
        return handle


class TestRadioPacketPayloads:
    """Validate radio payload normalization so downstream consumers see stable types."""

    def test_radio_packet_to_input_normalises_payload(self) -> None:
        """Verify byte payloads become unsigned integer lists so event consumers can serialize them consistently."""
        packet = RadioPacket(
            protocol="flowtoy",
            frequency_hz=2_439_000_000,
            channel=39,
            bitrate_kbps=250,
            modulation="GFSK",
            crc_ok=True,
            rssi_dbm=-42.5,
            payload=b"\x01\x02\xff",
            decoded={"schema": "flowtoy.sync.v1"},
            metadata={"manufacturer": "FlowToys"},
        )

        rendered = packet.to_input()

        assert rendered.event_type == RadioPacket.EVENT_TYPE
        assert rendered.data["protocol"] == "flowtoy"
        assert rendered.data["frequency_hz"] == 2_439_000_000.0
        assert rendered.data["channel"] == 39.0
        assert rendered.data["bitrate_kbps"] == 250.0
        assert rendered.data["modulation"] == "GFSK"
        assert rendered.data["crc_ok"] is True
        assert rendered.data["rssi_dbm"] == pytest.approx(-42.5)
        assert rendered.data["payload"] == [1, 2, 255]
        assert rendered.data["decoded"] == {"schema": "flowtoy.sync.v1"}
        assert rendered.data["metadata"] == {"manufacturer": "FlowToys"}


class TestRadioPeripheralDetectionAndStreaming:
    """Cover radio peripheral discovery and event publication so the host can both find and observe bridges."""

    def test_detect_wraps_serial_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify detection wraps discovered drivers so runtime wiring can add radio bridges without custom glue."""
        stub_driver = DummyDriver(packets=iter([RawRadioPacket()]))

        def _fake_detect(cls) -> Iterator[DummyDriver]:
            yield stub_driver

        monkeypatch.setattr(SerialRadioDriver, "detect", classmethod(_fake_detect))

        detected = list(RadioPeripheral.detect())

        assert detected
        assert detected[0].latest_packet is None
        assert detected[0]._driver is stub_driver

    def test_process_packet_updates_latest_and_publishes_event(self) -> None:
        """Ensure inbound packets update snapshots and emit a shared event so telemetry consumers stay synchronized."""
        peripheral = RadioPeripheral(driver=DummyDriver())
        observed: list[RadioPacket] = []

        subscription = peripheral.observe.subscribe(
            on_next=lambda envelope: observed.append(
                PeripheralMessageEnvelope[RadioPacket].unwrap_peripheral(envelope)
            )
        )
        try:
            packet = RawRadioPacket(
                payload=b"\x10\x20",
                protocol="flowtoy",
                frequency_hz=2_402_000_000,
                channel=2,
                bitrate_kbps=250,
                modulation="GFSK",
                crc_ok=True,
                rssi_dbm=-51.0,
                decoded={"schema": "flowtoy.sync.v1", "group_id": 1},
                metadata={"source": "bridge"},
            )

            peripheral.process_packet(packet)
        finally:
            subscription.dispose()

        assert peripheral.latest_packet == packet
        assert observed == [
            RadioPacket(
                protocol="flowtoy",
                frequency_hz=2_402_000_000,
                channel=2,
                bitrate_kbps=250,
                modulation="GFSK",
                crc_ok=True,
                rssi_dbm=-51.0,
                payload=b"\x10\x20",
                decoded={"schema": "flowtoy.sync.v1", "group_id": 1},
                metadata={"source": "bridge"},
            )
        ]

    def test_install_node_publishes_packets_to_manyfold_route(self) -> None:
        """Ensure the graph-native radio node publishes packet events without requiring .observe consumers."""
        packet = RawRadioPacket(
            payload=b"\x10\x20",
            protocol="flowtoy",
            rssi_dbm=-51.0,
        )
        peripheral = RadioPeripheral(driver=DummyDriver(packets=iter([packet])))
        graph = Graph()
        output = radio_packet_event_route()

        handle = peripheral.install_node(
            graph,
            output_route=output,
            start_immediately=False,
        )
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(output)
        assert latest is not None
        assert latest.value.event_type == RadioPacket.EVENT_TYPE
        assert latest.value.data["payload"] == [16, 32]
        assert latest.value.data["protocol"] == "flowtoy"
        assert peripheral.latest_packet == packet

    def test_install_node_publishes_exceptions_to_error_route(self) -> None:
        """Ensure managed node failures become route data for functional health handling."""
        peripheral = RadioPeripheral(driver=FailingDriver())
        graph = Graph()
        errors = radio_error_route()

        handle = peripheral.install_node(
            graph,
            error_route=errors,
            retry=RetryPolicy(max_attempts=1),
            backoff=BackoffPolicy.none(),
            start_immediately=False,
        )
        with pytest.raises(RuntimeError, match="radio unavailable"):
            handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(errors)
        assert latest is not None
        assert isinstance(latest.value, RuntimeError)
        assert "radio unavailable" in str(latest.value)

    def test_detection_node_publishes_only_when_radios_are_detected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure radio detection becomes a graph signal without forcing downstream streams to fire."""
        detected_peripheral = RadioPeripheral(driver=DummyDriver())

        def _detect(cls) -> Iterator[RadioPeripheral]:
            yield detected_peripheral

        monkeypatch.setattr(RadioPeripheral, "detect", classmethod(_detect))
        graph = Graph()
        route = radio_detection_route()
        registered: list[RadioPeripheral] = []

        handle = RadioPeripheral.detection_node(
            output_route=route,
            on_detect=lambda peripheral, _graph: registered.append(peripheral),
            start_immediately=False,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(route)
        assert latest is not None
        assert latest.value.event_type == "peripheral.radio.detected"
        assert latest.value.data["driver"] == "DummyDriver"
        assert registered == [detected_peripheral]

    def test_detection_node_stays_silent_when_no_radios_are_detected(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure absent hardware is represented by no route emission."""

        def _detect(cls) -> Iterator[RadioPeripheral]:
            return
            yield RadioPeripheral(driver=DummyDriver())

        monkeypatch.setattr(RadioPeripheral, "detect", classmethod(_detect))
        graph = Graph()
        route = radio_detection_route()

        handle = RadioPeripheral.detection_node(
            output_route=route,
            start_immediately=False,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        assert graph.latest(route) is None

    def test_detection_node_can_spawn_detected_radio_packet_sources(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure detection can install source nodes while renderers still own filtering."""
        packet = RawRadioPacket(payload=b"\x01", protocol="flowtoy")
        detected_peripheral = RadioPeripheral(
            driver=DummyDriver(packets=iter([packet]))
        )

        def _detect(cls) -> Iterator[RadioPeripheral]:
            yield detected_peripheral

        monkeypatch.setattr(RadioPeripheral, "detect", classmethod(_detect))
        graph = Graph()
        detection_route = radio_detection_route()
        packet_route = radio_packet_event_route()

        handle = RadioPeripheral.detection_node(
            output_route=detection_route,
            packet_output_route=packet_route,
            spawn_sources=True,
            start_immediately=False,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(handle.spawned_handles) == 1
        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(detection_route)
        latest_packet = graph.latest(packet_route)
        assert latest_detection is not None
        assert latest_packet is not None
        assert latest_detection.value.event_type == "peripheral.radio.detected"
        assert latest_packet.value.event_type == RadioPacket.EVENT_TYPE
        assert latest_packet.value.data["payload"] == [1]


class TestRadioPeripheralFlowToyCommands:
    """Validate Flowtoys command serialization so Heart can drive the first read-write sensor safely."""

    @pytest.mark.parametrize(
        ("event_type", "payload", "expected_command"),
        [
            (
                FLOWTOY_SYNC_EVENT,
                {"timeout_seconds": 1.5},
                "s1.5",
            ),
            (
                FLOWTOY_STOP_SYNC_EVENT,
                {},
                "S",
            ),
            (
                FLOWTOY_RESET_SYNC_EVENT,
                {},
                "a",
            ),
            (
                FLOWTOY_WAKE_EVENT,
                {"groupID": 3, "groupIsPublic": True},
                "W3",
            ),
            (
                FLOWTOY_RAW_COMMAND_EVENT,
                {"command": "z0"},
                "z0",
            ),
        ],
    )
    def test_handle_input_serializes_supported_commands(
        self,
        event_type: str,
        payload: dict[str, Any],
        expected_command: str,
    ) -> None:
        """Ensure each supported control event becomes the expected bridge command so runtime automation can remain declarative."""
        driver = DummyDriver()
        peripheral = RadioPeripheral(driver=driver)

        peripheral.handle_input(Input(event_type=event_type, data=payload))

        assert driver.commands == [expected_command]

    def test_handle_input_serializes_flowtoy_pattern_commands(self) -> None:
        """Verify pattern payloads preserve Flowtoys field order so bridge firmware applies the intended lighting state."""
        driver = DummyDriver()
        peripheral = RadioPeripheral(driver=driver)

        peripheral.handle_input(
            Input(
                event_type=FLOWTOY_PATTERN_EVENT,
                data={
                    "groupID": 4,
                    "groupIsPublic": True,
                    "page": 2,
                    "mode": 7,
                    "actives": 255,
                    "hueOffset": 120,
                    "saturation": 200,
                    "brightness": 180,
                    "speed": 90,
                    "density": 60,
                    "lfo1": 1,
                    "lfo2": 2,
                    "lfo3": 3,
                    "lfo4": 4,
                },
            )
        )

        assert driver.commands == ["P4,2,7,255,120,200,180,90,60,1,2,3,4"]

    def test_flowtoy_pattern_formats_private_groups(self) -> None:
        """Confirm private-group patterns use the lowercase prefix so Heart can target non-public props without address bleed."""
        pattern = FlowToyPattern(group_id=2, mode=5)

        assert pattern.to_serial_command() == "p2,0,5,0,0,0,0,0,0,0,0,0,0"


class TestSerialRadioDriverWrites:
    """Exercise serial command writes so host control stays correct even without real hardware attached in tests."""

    def test_send_raw_command_appends_newline(self) -> None:
        """Ensure outbound commands are newline framed so the Flowtoys bridge parser can delimit each request reliably."""
        serial_module = FakeSerialModule()
        driver = SerialRadioDriver(port="/dev/null", serial_module=serial_module)

        driver.send_raw_command("S")

        assert len(serial_module.handles) == 1
        assert serial_module.handles[0].writes == [b"S\n"]
        assert serial_module.handles[0].flushed is True

    def test_identify_returns_bridge_metadata(self) -> None:
        """Verify identify queries reuse the serial driver so higher-level tooling can discover the correct bridge without bespoke serial code."""
        serial_module = FakeSerialModule()
        driver = SerialRadioDriver(port="/dev/null", serial_module=serial_module)

        def _serial(*_args: Any, **_kwargs: Any) -> FakeSerialHandle:
            handle = FakeSerialHandle()
            handle.lines = [
                b'{"event_type":"device.identify","data":{"device_name":"feather-flowtoy-bridge","protocol":"flowtoy","mode":"receive-only"}}\n'
            ]
            serial_module.handles.append(handle)
            return handle

        serial_module.Serial = _serial  # type: ignore[method-assign]

        identity = driver.identify(ready_delay=0, timeout_seconds=0.01, attempts=1)

        assert identity == {
            "device_name": "feather-flowtoy-bridge",
            "protocol": "flowtoy",
            "mode": "receive-only",
        }
        assert serial_module.handles[0].writes == [b"Identify\n"]
        assert serial_module.handles[0].reset_calls == 1

    def test_read_messages_decodes_radio_packets(self) -> None:
        """Ensure bounded message reads return parsed packet events so operator tooling can inspect live traffic through the shared driver."""
        serial_module = FakeSerialModule()
        driver = SerialRadioDriver(port="/dev/null", serial_module=serial_module)

        def _serial(*_args: Any, **_kwargs: Any) -> FakeSerialHandle:
            handle = FakeSerialHandle()
            handle.lines = [
                b'{"event_type":"peripheral.radio.packet","data":{"protocol":"flowtoy","payload":[1,2,3],"rssi_dbm":-42}}\n'
            ]
            serial_module.handles.append(handle)
            return handle

        serial_module.Serial = _serial  # type: ignore[method-assign]

        messages = list(driver.read_messages(duration_seconds=0.01, ready_delay=0))

        assert len(messages) == 1
        assert messages[0].event_type == "peripheral.radio.packet"
        assert messages[0].packet is not None
        assert messages[0].packet.protocol == "flowtoy"
        assert messages[0].packet.payload == b"\x01\x02\x03"

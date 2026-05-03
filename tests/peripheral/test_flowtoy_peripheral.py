from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.flowtoy import FlowToyPeripheral
from heart.peripheral.input_payloads import FlowToyPacket
from heart.peripheral.radio import (RadioDriver, RawRadioPacket,
                                    SerialRadioDriver)


class DummyDriver(RadioDriver):
    """Provide deterministic packet streams so FlowToy peripheral behavior stays testable."""

    def __init__(self, packets: Iterator[RawRadioPacket] | None = None, *, port: str = "/dev/ttyACM0") -> None:
        self._packets = list(packets or [])
        self.port = port
        self.closed = False
        self.commands: list[str] = []

    def packets(self) -> Iterator[RawRadioPacket]:
        yield from self._packets

    def send_raw_command(self, command: str) -> None:
        self.commands.append(command)

    def close(self) -> None:
        self.closed = True


class TestFlowToyPacketPayloads:
    """Validate FlowToy payload materialization so the peripheral exposes the full bridge JSON body."""

    def test_to_input_preserves_body_and_mode_name(self) -> None:
        """Verify FlowToy packet payloads keep the full bridge body so higher-level consumers do not lose radio context."""
        packet = FlowToyPacket(
            body={"protocol": "flowtoy", "decoded": {"page": 2, "mode": 1}},
            mode_name="flowtoy-page-2-mode-1",
        )

        rendered = packet.to_input()

        assert rendered.event_type == FlowToyPacket.EVENT_TYPE
        assert rendered.data == {
            "protocol": "flowtoy",
            "decoded": {"page": 2, "mode": 1},
            "mode_name": "flowtoy-page-2-mode-1",
        }


class TestFlowToyPeripheralDetectionAndStreaming:
    """Cover FlowToy-specific detection and dynamic naming so the ecosystem sees a first-class peripheral instead of raw radio bytes."""

    def test_detect_wraps_serial_driver(self, monkeypatch) -> None:
        """Verify detection wraps discovered radio drivers so the default configuration can surface FlowToy devices automatically."""
        stub_driver = DummyDriver()

        def _fake_detect(cls) -> Iterator[DummyDriver]:
            yield stub_driver

        monkeypatch.setattr(SerialRadioDriver, "detect", classmethod(_fake_detect))

        detected = list(FlowToyPeripheral.detect())

        assert len(detected) == 1
        assert detected[0]._driver is stub_driver

    def test_process_packet_publishes_full_body_and_dynamic_mode_info(self) -> None:
        """Ensure FlowToy packets emit the complete JSON body and mode-derived tags so downstream routing can key off the active prop state."""
        peripheral = FlowToyPeripheral(driver=DummyDriver(port="/dev/ttyACM3"))
        observed: list[tuple[Any, FlowToyPacket]] = []

        subscription = peripheral.observe.subscribe(
            on_next=lambda envelope: observed.append(
                (
                    envelope.peripheral_info,
                    PeripheralMessageEnvelope[FlowToyPacket].unwrap_peripheral(envelope),
                )
            )
        )
        try:
            peripheral.process_packet(
                RawRadioPacket(
                    payload=bytes(
                        [
                            0x00,
                            0x01,
                            0x02,
                            0x00,
                            0x00,
                            0x00,
                            0x01,
                            0x02,
                            0x03,
                            0x04,
                            10,
                            20,
                            30,
                            40,
                            50,
                            0b0000_0011,
                            0x00,
                            0x00,
                            2,
                            7,
                            0b0000_0010,
                        ]
                    ),
                    protocol="flowtoy",
                    channel=2,
                    bitrate_kbps=250,
                    modulation="nrf24-shockburst",
                    crc_ok=True,
                    rssi_dbm=-42.0,
                    metadata={"receiver": "nrf52840"},
                )
            )
        finally:
            subscription.dispose()

        peripheral_info, packet = observed[0]
        assert packet.body == {
            "protocol": "flowtoy",
            "channel": 2.0,
            "bitrate_kbps": 250.0,
            "modulation": "nrf24-shockburst",
            "crc_ok": True,
            "rssi_dbm": -42.0,
            "payload": [0, 1, 2, 0, 0, 0, 1, 2, 3, 4, 10, 20, 30, 40, 50, 3, 0, 0, 2, 7, 2],
            "decoded": {
                "schema": "flowtoy.sync.v1",
                "group_id": 1,
                "padding": 2,
                "lfo": [1, 2, 3, 4],
                "global": {
                    "hue": 10,
                    "saturation": 20,
                    "brightness": 30,
                    "speed": 40,
                    "density": 50,
                },
                "active_flags": {
                    "lfo": True,
                    "hue": True,
                    "saturation": False,
                    "brightness": False,
                    "speed": False,
                    "density": False,
                },
                "reserved": [0, 0],
                "page": 2,
                "mode": 7,
                "mode_name": "flowtoy-page-2-mode-7",
                "mode_documentation": {
                    "page": 2,
                    "mode": 7,
                    "key": "flowtoy-page-2-mode-7",
                    "display_name": "unicorn",
                    "adjust": ["rainbow_brightness"],
                    "kinetic_trigger": ["low_force"],
                    "kinetic_response": ["activate_effect"],
                    "runtime": {
                        "static_hours": 9,
                        "kinetic_hours": 5,
                        "qualifier": "approx_plus",
                    },
                    "color_spectrum": [
                        {"t": 0.0, "hex": "#ffd6f6"},
                        {"t": 0.25, "hex": "#d9c2ff"},
                        {"t": 0.5, "hex": "#9be7ff"},
                        {"t": 0.75, "hex": "#b8ffd6"},
                        {"t": 1.0, "hex": "#fffdf7"},
                    ],
                    "source_url": "https://flowtoys2.freshdesk.com/support/solutions/articles/6000229509-capsule-v2-modes-adjust-kinetic-and-runtimes",
                },
                "command_flags": {
                    "adjust_active": False,
                    "wakeup": True,
                    "poweroff": False,
                    "force_reload": False,
                    "save": False,
                    "delete": False,
                    "alternate": False,
                },
            },
            "metadata": {"receiver": "nrf52840"},
        }
        assert packet.mode_name == "flowtoy-page-2-mode-7"
        assert peripheral_info.id == "flowtoy_dev_ttyacm3_flowtoy-page-2-mode-7"
        assert {(tag.name, tag.variant) for tag in peripheral_info.tags} == {
            ("input_variant", "flowtoy"),
            ("mode", "flowtoy-page-2-mode-7"),
        }

    def test_process_packet_ignores_non_flowtoy_protocols(self) -> None:
        """Verify non-FlowToy radio packets are ignored so unrelated bridges do not masquerade as FlowToy peripherals."""
        peripheral = FlowToyPeripheral(driver=DummyDriver())
        observed: list[FlowToyPacket] = []

        subscription = peripheral.observe.subscribe(
            on_next=lambda envelope: observed.append(
                PeripheralMessageEnvelope[FlowToyPacket].unwrap_peripheral(envelope)
            )
        )
        try:
            peripheral.process_packet(
                RawRadioPacket(payload=b"\x01\x02", protocol="zigbee")
            )
        finally:
            subscription.dispose()

        assert observed == []

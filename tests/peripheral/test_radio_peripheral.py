from __future__ import annotations

from typing import Iterator

import pytest

from heart.events.types import RadioPacket
from heart.peripheral.radio import (RadioDriver, RadioPeripheral,
                                    RawRadioPacket, SerialRadioDriver)


class DummyDriver(RadioDriver):
    def __init__(self, packets: Iterator[RawRadioPacket] | None = None) -> None:
        self._packets = list(packets or [])
        self.closed = False

    def packets(self) -> Iterator[RawRadioPacket]:
        yield from self._packets

    def close(self) -> None:
        self.closed = True


class TestPeripheralRadioPeripheral:
    """Group Peripheral Radio Peripheral tests so peripheral radio peripheral behaviour stays reliable. This preserves confidence in peripheral radio peripheral for end-to-end scenarios."""

    def test_radio_packet_to_input_normalises_payload(self) -> None:
        """Verify that radio packet to input normalises payload. This keeps hardware telemetry responsive for interactive experiences."""
        packet = RadioPacket(
            frequency_hz=2_439_000_000,
            channel=39,
            modulation="GFSK",
            rssi_dbm=-42.5,
            payload=b"\x01\x02\xFF",
            metadata={"manufacturer": "FlowToys"},
        )

        rendered = packet.to_input()

        assert rendered.event_type == RadioPacket.EVENT_TYPE
        assert rendered.data["frequency_hz"] == 2_439_000_000.0
        assert rendered.data["channel"] == 39.0
        assert rendered.data["modulation"] == "GFSK"
        assert rendered.data["rssi_dbm"] == pytest.approx(-42.5)
        assert rendered.data["payload"] == [1, 2, 255]
        assert rendered.data["metadata"] == {"manufacturer": "FlowToys"}



    def test_process_packet_emits_event(self) -> None:
        """Verify that process packet emits event. This ensures event orchestration remains reliable."""
        captured: list[dict] = []

        def _capture(event):
            captured.append(event.data)

        # subscribe(RadioPeripheral.EVENT_TYPE, _capture)

        driver = DummyDriver()
        peripheral = RadioPeripheral(driver=driver)

        sample = RawRadioPacket(
            payload=b"\xAA\xBB",
            frequency_hz=2_439_000_000,
            channel=39,
            modulation="GFSK",
            rssi_dbm=-50.0,
            metadata={"hop": 0},
        )

        peripheral.process_packet(sample)

        assert peripheral.latest_packet is sample
        assert captured
        emitted = captured[-1]
        assert emitted["payload"] == [170, 187]
        assert emitted["frequency_hz"] == 2_439_000_000.0
        assert emitted["channel"] == 39.0
        assert emitted["modulation"] == "GFSK"
        assert emitted["rssi_dbm"] == pytest.approx(-50.0)
        assert emitted["metadata"] == {"hop": 0}



    def test_detect_wraps_serial_driver(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that detect wraps serial driver. This keeps the system behaviour reliable for operators."""
        packets = iter([RawRadioPacket()])
        stub_driver = DummyDriver(packets=packets)

        def _fake_detect(cls):
            yield stub_driver

        monkeypatch.setattr(SerialRadioDriver, "detect", classmethod(_fake_detect))

        detected = list(RadioPeripheral.detect())

        assert detected
        assert detected[0].latest_packet is None
        assert detected[0]._driver is stub_driver

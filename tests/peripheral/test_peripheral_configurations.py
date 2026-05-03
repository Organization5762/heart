from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph

from heart.peripheral.configurations import (_detect_radios,
                                             _radio_detection_node)
from heart.peripheral.input_payloads import RadioPacket
from heart.peripheral.radio import (RadioDriver, RadioPeripheral,
                                    RawRadioPacket, SerialRadioDriver,
                                    radio_detection_route,
                                    radio_packet_event_route)


class _DriverStub(RadioDriver):
    def __init__(self, packets: Iterator[RawRadioPacket] | None = None) -> None:
        self._packets = tuple(packets or ())
        self.commands: list[str] = []
        self.closed = False

    def packets(self) -> Iterator[RawRadioPacket]:
        yield from self._packets

    def send_raw_command(self, command: str) -> None:
        self.commands.append(command)

    def close(self) -> None:
        self.closed = True


class TestManyfoldRadioConfiguration:
    """Cover default graph-node factories so generic radio bridges stay Manyfold-owned."""

    def test_detect_radios_wraps_serial_radio_as_generic_peripheral(
        self,
        monkeypatch,
    ) -> None:
        driver = _DriverStub()

        def _detect(cls) -> Iterator[_DriverStub]:
            yield driver

        monkeypatch.setattr(SerialRadioDriver, "detect", classmethod(_detect))

        radios = list(_detect_radios())

        assert len(radios) == 1
        assert isinstance(radios[0], RadioPeripheral)
        assert radios[0]._driver is driver

    def test_radio_detection_node_spawns_generic_packet_source(
        self,
        monkeypatch,
    ) -> None:
        packet = RawRadioPacket(payload=b"\x10", protocol="flowtoy")
        detected = RadioPeripheral(driver=_DriverStub(packets=iter([packet])))

        def _detect(cls) -> Iterator[RadioPeripheral]:
            yield detected

        monkeypatch.setattr(RadioPeripheral, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[RadioPeripheral] = []

        handle = _radio_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert registered == [detected]
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(radio_detection_route())
        latest_packet = graph.latest(radio_packet_event_route())
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.radio.detected"
        assert latest_packet is not None
        assert latest_packet.value.event_type == RadioPacket.EVENT_TYPE
        assert latest_packet.value.data["payload"] == [16]

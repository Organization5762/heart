from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph

from heart.peripheral.configurations import (_detect_radios,
                                             _microphone_detection_node,
                                             _radio_detection_node)
from heart.peripheral.input_payloads import MicrophoneLevel, RadioPacket
from heart.peripheral.microphone import (Microphone,
                                         microphone_detection_route,
                                         microphone_level_event_route)
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


class TestManyfoldMicrophoneConfiguration:
    """Cover default graph-node factories so microphone streams stay Manyfold-owned."""

    def test_microphone_detection_node_spawns_level_source(
        self,
        monkeypatch,
    ) -> None:
        detected = Microphone()
        level = MicrophoneLevel(
            rms=0.5,
            peak=1.0,
            frames=16,
            samplerate=16_000,
            timestamp=123.0,
        )

        def _detect(cls) -> Iterator[Microphone]:
            yield detected

        def _install_node(self, graph: Graph, **kwargs):
            graph.publish(
                kwargs["output_route"],
                self._level_to_sensor_event(level),
            )
            return object()

        monkeypatch.setattr(Microphone, "detect", classmethod(_detect))
        monkeypatch.setattr(Microphone, "install_node", _install_node)
        graph = Graph()
        registered: list[Microphone] = []

        handle = _microphone_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(microphone_detection_route())
        latest_level = graph.latest(microphone_level_event_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.microphone.detected"
        assert latest_level is not None
        assert latest_level.value.event_type == MicrophoneLevel.EVENT_TYPE
        assert latest_level.value.data["rms"] == 0.5

from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph

from heart.peripheral.configurations import (_accelerometer_detection_node,
                                             _detect_gamepads,
                                             _detect_heart_rate_sensor,
                                             _detect_radios, _detect_switches,
                                             _gamepad_detection_node,
                                             _heart_rate_detection_node,
                                             _manyfold_graph_nodes,
                                             _microphone_detection_node,
                                             _radio_detection_node,
                                             _switch_detection_node)
from heart.peripheral.configurations.default import configure
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.gamepad.gamepad import gamepad_detection_route
from heart.peripheral.input_payloads import MicrophoneLevel, RadioPacket
from heart.peripheral.microphone import (Microphone,
                                         microphone_detection_route,
                                         microphone_level_event_route)
from heart.peripheral.radio import (RadioDriver, RadioPeripheral,
                                    RawRadioPacket, SerialRadioDriver,
                                    radio_detection_route,
                                    radio_packet_event_route)
from heart.peripheral.sensor import (Accelerometer,
                                     accelerometer_detection_route,
                                     accelerometer_vector_event_route)


class _SerialStub:
    def __init__(self, packets: Iterator[bytes]) -> None:
        self._packets = packets

    def __enter__(self) -> "_SerialStub":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def readline(self) -> bytes:
        try:
            return next(self._packets)
        except StopIteration:
            raise KeyboardInterrupt


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


class TestManyfoldAccelerometerConfiguration:
    """Cover default graph-node factories so connected IMU streams stay Manyfold-owned."""

    def test_accelerometer_detection_node_spawns_vector_source(
        self,
        monkeypatch,
    ) -> None:
        payload = b'{"event_type":"sensor.acceleration","data":{"x":1,"y":2,"z":3}}\n'
        detected = Accelerometer(port="/dev/ttyUSB0", baudrate=115200)

        def _detect(cls) -> Iterator[Accelerometer]:
            yield detected

        monkeypatch.setattr(Accelerometer, "detect", classmethod(_detect))
        monkeypatch.setattr(
            detected,
            "_connect_to_ser",
            lambda: _SerialStub(iter((payload,))),
        )
        graph = Graph()
        registered: list[Accelerometer] = []

        handle = _accelerometer_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert registered == [detected]
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(accelerometer_detection_route())
        latest_vector = graph.latest(accelerometer_vector_event_route())
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.accelerometer.detected"
        assert latest_vector is not None
        assert latest_vector.value.event_type == "peripheral.accelerometer.vector"
        assert latest_vector.value.data == {"x": 1.0, "y": 2.0, "z": 3.0}

    def test_manyfold_graph_nodes_include_accelerometer_on_pi(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_pi",
            lambda: True,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_x11_forward",
            lambda: False,
        )

        nodes = _manyfold_graph_nodes()

        assert _accelerometer_detection_node in nodes

    def test_manyfold_graph_nodes_keep_fake_accelerometer_direct_off_pi(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_x11_forward",
            lambda: False,
        )

        nodes = _manyfold_graph_nodes()

        assert _accelerometer_detection_node not in nodes


class TestManyfoldGamepadConfiguration:
    """Cover default graph-node factories so gamepad discovery stays Manyfold-owned."""

    def test_gamepad_detection_node_publishes_detection_event(
        self,
        monkeypatch,
    ) -> None:
        detected = Gamepad(joystick_id=2)

        def _detect(cls) -> Iterator[Gamepad]:
            yield detected

        monkeypatch.setattr(Gamepad, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[Gamepad] = []

        handle = _gamepad_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(gamepad_detection_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.gamepad.detected"
        assert latest_detection.value.data == {
            "joystick_id": 2,
            "connected": False,
            "name": None,
        }
        assert latest_detection.value.identity.id == "gamepad:2"

    def test_default_configuration_moves_gamepad_to_graph_node(self) -> None:
        configuration = configure()

        assert _gamepad_detection_node in configuration.graph_nodes
        assert _detect_gamepads not in configuration.detectors


class TestManyfoldSwitchConfiguration:
    """Cover default graph-node factories so physical switch streams stay Manyfold-owned."""

    def test_manyfold_graph_nodes_include_physical_switch_on_pi(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.use_mock_switch",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_pi",
            lambda: True,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_x11_forward",
            lambda: False,
        )

        nodes = _manyfold_graph_nodes()

        assert nodes[0] is _switch_detection_node

    def test_default_configuration_moves_physical_switch_to_graph_node(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.use_mock_switch",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_pi",
            lambda: True,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_x11_forward",
            lambda: False,
        )

        configuration = configure()

        assert _switch_detection_node in configuration.graph_nodes
        assert _detect_switches not in configuration.detectors

    def test_default_configuration_keeps_switch_direct_for_local_fake(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.use_mock_switch",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.configurations.Configuration.is_x11_forward",
            lambda: False,
        )

        configuration = configure()

        assert _switch_detection_node not in configuration.graph_nodes
        assert configuration.detectors[0] is _detect_switches


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


class TestManyfoldHeartRateConfiguration:
    """Cover default graph-node factories so ANT+ heart-rate streams stay Manyfold-owned."""

    def test_default_configuration_moves_heart_rate_to_graph_node(self) -> None:
        configuration = configure()

        assert _heart_rate_detection_node in configuration.graph_nodes
        assert _detect_heart_rate_sensor not in configuration.detectors

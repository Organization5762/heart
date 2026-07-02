from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from manyfold import Graph
from pytest import MonkeyPatch

from heart.peripheral.compass import Compass, compass_detection_route
from heart.peripheral.configurations import (
    _accelerometer_detection_node, _compass_detection_node, _detect_radios,
    _drawing_pad_detection_node, _fake_accelerometer_detection_node,
    _gamepad_detection_node, _manyfold_graph_nodes, _microphone_detection_node,
    _phone_text_detection_node, _radio_detection_node, _switch_detection_node,
    _uwb_detection_node)
from heart.peripheral.core.manager import GRAPH_OWNED_PERIPHERAL_ATTR
from heart.peripheral.drawing_pad import (DrawingPad,
                                          drawing_pad_detection_route,
                                          drawing_pad_sample_event_route)
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.gamepad.gamepad import (DEFAULT_GAMEPAD_SLOTS,
                                              gamepad_detection_route)
from heart.peripheral.input_payloads import MicrophoneLevel, RadioPacket
from heart.peripheral.microphone import (Microphone,
                                         microphone_detection_route,
                                         microphone_level_event_route)
from heart.peripheral.phone_text import (PhoneText, phone_text_detection_route,
                                         phone_text_message_route)
from heart.peripheral.radio import (RadioDriver, RadioPeripheral,
                                    RawRadioPacket, SerialRadioDriver,
                                    radio_detection_route,
                                    radio_packet_event_route)
from heart.peripheral.sensor import (Accelerometer, FakeAccelerometer,
                                     accelerometer_detection_route,
                                     accelerometer_vector_event_route,
                                     magnetometer_vector_event_route)
from heart.peripheral.switch import FakeSwitch, Switch
from heart.peripheral.uwb import (BaseStationMeasurement, FakeUWBPositioning,
                                  LocalizedTarget, uwb_detection_route,
                                  uwb_position_event_route)


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
        assert getattr(detected, GRAPH_OWNED_PERIPHERAL_ATTR) is True
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

    def test_accelerometer_detection_node_spawns_magnetometer_source(
        self,
        monkeypatch,
    ) -> None:
        payload = b'{"event_type":"sensor.magnetic","data":{"x":7,"y":8,"z":9}}\n'
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

        handle = _accelerometer_detection_node(
            start_immediately=False,
            on_detect=None,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(accelerometer_detection_route())
        latest_vector = graph.latest(magnetometer_vector_event_route())
        assert latest_detection is not None
        assert latest_vector is not None
        assert latest_vector.value.event_type == "peripheral.magnetometer.vector"
        assert latest_vector.value.data == {"x": 7.0, "y": 8.0, "z": 9.0}

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

    def test_compass_detection_node_spawns_compass_source(
        self,
        monkeypatch,
    ) -> None:
        detected = Compass()

        def _detect(cls) -> Iterator[Compass]:
            yield detected

        monkeypatch.setattr(Compass, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[Compass] = []

        handle = _compass_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(compass_detection_route())
        assert registered == [detected]
        assert len(handle.spawned_handles) == 1
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.compass.detected"

    def test_manyfold_graph_nodes_include_compass_on_pi(
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

        assert _compass_detection_node in nodes

    def test_manyfold_graph_nodes_include_fake_accelerometer_off_pi(
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
        assert _fake_accelerometer_detection_node in nodes

    def test_fake_accelerometer_detection_node_spawns_vector_source(
        self,
        monkeypatch,
    ) -> None:
        original_install_node = FakeAccelerometer.install_node

        def _install_node(
            self: FakeAccelerometer,
            graph: Graph,
            **kwargs: Any,
        ) -> Any:
            return original_install_node(
                self,
                graph,
                **kwargs,
                sample_interval_seconds=0,
            )

        monkeypatch.setattr(FakeAccelerometer, "install_node", _install_node)
        graph = Graph()
        registered: list[FakeAccelerometer] = []

        handle = _fake_accelerometer_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(registered) == 1
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_detection = graph.latest(accelerometer_detection_route())
        latest_vector = graph.latest(accelerometer_vector_event_route())
        assert latest_detection is not None
        assert latest_detection.value.identity.id == "fake_accelerometer"
        assert latest_vector is not None
        assert latest_vector.value.event_type == "peripheral.accelerometer.vector"
        assert latest_vector.value.identity.id == "fake_accelerometer"

class TestManyfoldGamepadConfiguration:
    """Cover default graph-node factories so gamepad discovery stays Manyfold-owned."""

    def test_gamepad_detection_enumerates_joystick_slots(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.joystick.quit", lambda: None
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.joystick.init", lambda: None
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.joystick.get_count", lambda: 0
        )

        gamepads = list(Gamepad.detect())

        assert [gamepad.joystick_id for gamepad in gamepads] == list(
            range(DEFAULT_GAMEPAD_SLOTS)
        )

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

class TestManyfoldDrawingPadConfiguration:
    """Cover default graph-node factories so virtual drawing pads stay Manyfold-owned."""

    def test_drawing_pad_detection_node_spawns_sample_source(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        detected = DrawingPad()

        def _detect(cls) -> Iterator[DrawingPad]:
            yield detected

        def _install_node(
            self: DrawingPad,
            graph: Graph,
            **kwargs: Any,
        ) -> object:
            graph.publish(
                kwargs["output_route"],
                self._sample_to_sensor_event(
                    self._parse_payload(
                        {"x": 0.5, "y": 0.25, "pressure": 0.6},
                        is_erase=False,
                    )["sample"]
                ),
            )
            return object()

        monkeypatch.setattr(DrawingPad, "detect", classmethod(_detect))
        monkeypatch.setattr(DrawingPad, "install_node", _install_node)
        graph = Graph()
        registered: list[DrawingPad] = []

        handle = _drawing_pad_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(drawing_pad_detection_route())
        latest_sample = graph.latest(drawing_pad_sample_event_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.drawing_pad.detected"
        assert latest_sample is not None
        assert latest_sample.value.event_type == "peripheral.drawing_pad.sample"
        assert latest_sample.value.data["pressure"] == 0.6

class TestManyfoldSwitchConfiguration:
    """Cover default graph-node factories so switch streams stay Manyfold-owned."""

    def test_switch_detection_marks_only_real_switches_graph_owned(
        self,
        monkeypatch,
    ) -> None:
        real_switch = Switch(port="/dev/null", baudrate=115200)
        fake_switch = FakeSwitch()

        def _detect() -> Iterator[object]:
            yield real_switch
            yield fake_switch

        monkeypatch.setattr("heart.peripheral.configurations._detect_switches", _detect)
        registered: list[object] = []
        handle = _switch_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(Graph())

        handle.loop_handle.loop.run(handle.loop_handle.token)

        assert registered == [real_switch, fake_switch]
        assert getattr(real_switch, GRAPH_OWNED_PERIPHERAL_ATTR) is True
        assert not getattr(fake_switch, GRAPH_OWNED_PERIPHERAL_ATTR, False)

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


class TestManyfoldPhoneTextConfiguration:
    """Cover default graph-node factories so BLE text input stays Manyfold-owned."""

    def test_phone_text_detection_node_spawns_message_source(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        detected = PhoneText()

        def _detect(cls) -> Iterator[PhoneText]:
            yield detected

        def _install_node(
            self: PhoneText,
            graph: Graph,
            **kwargs: Any,
        ) -> object:
            graph.publish(
                kwargs["output_route"],
                self._text_to_sensor_event("hello"),
            )
            return object()

        monkeypatch.setattr(PhoneText, "detect", classmethod(_detect))
        monkeypatch.setattr(PhoneText, "install_node", _install_node)
        graph = Graph()
        registered: list[PhoneText] = []

        handle = _phone_text_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(phone_text_detection_route())
        latest_message = graph.latest(phone_text_message_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.phone_text.detected"
        assert latest_message is not None
        assert latest_message.value.event_type == "peripheral.phone_text.message"
        assert latest_message.value.data == {"text": "hello"}

class TestManyfoldUWBConfiguration:
    """Cover default graph-node factories so UWB positioning stays Manyfold-owned."""

    def test_uwb_detection_node_spawns_position_source(
        self,
        monkeypatch: MonkeyPatch,
    ) -> None:
        detected = FakeUWBPositioning()
        target = LocalizedTarget(
            x=1.0,
            y=2.0,
            z=3.0,
            stations=[
                BaseStationMeasurement(
                    station_id="bs_0",
                    x=0.0,
                    y=0.0,
                    z=2.5,
                    distance=3.5,
                )
            ],
        )

        def _detect(cls) -> Iterator[FakeUWBPositioning]:
            yield detected

        def _install_node(
            self: FakeUWBPositioning,
            graph: Graph,
            **kwargs: Any,
        ) -> object:
            graph.publish(
                kwargs["output_route"],
                self._target_to_sensor_event(target),
            )
            return object()

        monkeypatch.setattr(FakeUWBPositioning, "detect", classmethod(_detect))
        monkeypatch.setattr(FakeUWBPositioning, "install_node", _install_node)
        graph = Graph()
        registered: list[FakeUWBPositioning] = []

        handle = _uwb_detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(uwb_detection_route())
        latest_position = graph.latest(uwb_position_event_route())
        assert registered == [detected]
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.uwb.detected"
        assert latest_position is not None
        assert latest_position.value.event_type == "peripheral.uwb.position"
        assert latest_position.value.data["stations"][0]["station_id"] == "bs_0"

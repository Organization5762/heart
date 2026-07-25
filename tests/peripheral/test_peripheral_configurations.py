from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph

from heart.peripheral.configurations import (
    _accelerometer_detection_node, _compass_detection_node,
    _fake_accelerometer_detection_node, _gamepad_detection_node,
    _manyfold_graph_nodes, _switch_detection_node)
from heart.peripheral.core.manager import GRAPH_OWNED_PERIPHERAL_ATTR
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.gamepad.gamepad import DEFAULT_GAMEPAD_SLOTS
from heart.peripheral.sensor import Accelerometer
from heart.peripheral.switch import FakeSwitch, Switch


def test_manyfold_graph_uses_physical_pi_inputs_and_local_fallbacks(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "heart.peripheral.configurations.Configuration.is_x11_forward",
        lambda: False,
    )
    monkeypatch.setattr(
        "heart.peripheral.configurations.Configuration.is_pi",
        lambda: True,
    )
    pi_nodes = _manyfold_graph_nodes()
    assert _switch_detection_node in pi_nodes
    assert _accelerometer_detection_node in pi_nodes
    assert _compass_detection_node in pi_nodes
    assert _fake_accelerometer_detection_node not in pi_nodes

    monkeypatch.setattr(
        "heart.peripheral.configurations.Configuration.is_pi",
        lambda: False,
    )
    local_nodes = _manyfold_graph_nodes()
    assert _accelerometer_detection_node not in local_nodes
    assert _compass_detection_node not in local_nodes
    assert _fake_accelerometer_detection_node in local_nodes
    assert _gamepad_detection_node in local_nodes


def test_gamepad_detection_reserves_stable_slots(monkeypatch) -> None:
    monkeypatch.setattr(
        "heart.peripheral.gamepad.gamepad.pygame.joystick.quit",
        lambda: None,
    )
    monkeypatch.setattr(
        "heart.peripheral.gamepad.gamepad.pygame.joystick.init",
        lambda: None,
    )
    monkeypatch.setattr(
        "heart.peripheral.gamepad.gamepad.pygame.joystick.get_count",
        lambda: 0,
    )

    assert [gamepad.joystick_id for gamepad in Gamepad.detect()] == list(
        range(DEFAULT_GAMEPAD_SLOTS)
    )


def test_real_switches_are_graph_owned_but_local_fallbacks_are_not(
    monkeypatch,
) -> None:
    real_switch = Switch(port="/dev/null", baudrate=115200)
    fake_switch = FakeSwitch()

    def detect() -> Iterator[object]:
        yield real_switch
        yield fake_switch

    monkeypatch.setattr("heart.peripheral.configurations._detect_switches", detect)
    handle = _switch_detection_node(
        start_immediately=False,
        on_detect=None,
    ).install(Graph())

    handle.loop_handle.loop.run(handle.loop_handle.token)

    assert getattr(real_switch, GRAPH_OWNED_PERIPHERAL_ATTR) is True
    assert not getattr(fake_switch, GRAPH_OWNED_PERIPHERAL_ATTR, False)


def test_detected_accelerometers_are_graph_owned(monkeypatch) -> None:
    accelerometer = Accelerometer(port="/dev/null", baudrate=115200)

    def detect(cls) -> Iterator[Accelerometer]:
        yield accelerometer

    monkeypatch.setattr(Accelerometer, "detect", classmethod(detect))
    handle = _accelerometer_detection_node(
        start_immediately=False,
        on_detect=None,
    ).install(Graph())

    handle.loop_handle.loop.run(handle.loop_handle.token)

    assert getattr(accelerometer, GRAPH_OWNED_PERIPHERAL_ATTR) is True

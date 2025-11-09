import pytest

from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.display.renderers.multi_scene import MultiScene
from heart.display.renderers.text import TextRendering
from heart.firmware_io.constants import BUTTON_PRESS, SWITCH_ROTATION
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.core.manager import PeripheralManager


class _StubScene(BaseRenderer):
    def __init__(self, label: str) -> None:
        super().__init__()
        self.label = label

    def get_renderers(self, peripheral_manager):  # pragma: no cover - trivial
        return [self]


def _disable_deprecated_switch(
    manager: PeripheralManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fail() -> None:  # pragma: no cover - defensive guard
        raise AssertionError("deprecated switch path accessed")

    monkeypatch.setattr(manager, "_deprecated_get_main_switch", _fail)


def test_text_rendering_reads_switch_from_event_bus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = EventBus()
    manager = PeripheralManager(event_bus=bus)
    manager.get_switch_state_consumer()
    _disable_deprecated_switch(manager, monkeypatch)

    bus.emit(SWITCH_ROTATION, 3)
    bus.emit(BUTTON_PRESS, 1)
    bus.emit(SWITCH_ROTATION, 5)

    renderer = TextRendering(
        text=["zero", "one", "two", "three"],
        font="Roboto",
        font_size=12,
        color=Color(0, 0, 0),
    )

    assert renderer._current_text(manager) == "two"


def test_multi_scene_updates_index_from_event_bus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = EventBus()
    manager = PeripheralManager(event_bus=bus)
    manager.get_switch_state_consumer()
    _disable_deprecated_switch(manager, monkeypatch)

    bus.emit(BUTTON_PRESS, 1)
    bus.emit(BUTTON_PRESS, 1)

    scenes = [_StubScene(label) for label in ("A", "B", "C")]
    multi_scene = MultiScene(scenes)

    multi_scene._process_switch(manager)

    assert multi_scene.current_scene_index == 2

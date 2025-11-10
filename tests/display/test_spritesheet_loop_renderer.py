import os
from collections import deque

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from heart.assets import loader as assets_loader
from heart.device import Rectangle
from heart.display.renderers.spritesheet import (BoundingBox, FrameDescription,
                                                 LoopPhase, Size,
                                                 SpritesheetLoop)
from heart.peripheral.switch import SwitchState


class _StubClock:
    def __init__(self, *times: int) -> None:
        self._times: deque[int] = deque(times)
        self._last: int = 0

    def get_time(self) -> int:
        if self._times:
            self._last = self._times.popleft()
        return self._last


class _StubSpritesheet:
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, int, int]] = []

    def get_size(self) -> tuple[int, int]:
        return (192, 64)

    def image_at(self, rect: tuple[int, int, int, int]) -> pygame.Surface:
        self.calls.append(rect)
        surface = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        surface.fill((255, 0, 0, 255))
        return surface


class _StubGamepad:
    def __init__(self, *, connected: bool = False) -> None:
        self._connected = connected
        self.axis_thresholds: dict[int, bool] = {}

    def is_connected(self) -> bool:
        return self._connected

    def axis_passed_threshold(self, axis: int) -> bool:
        return self.axis_thresholds.get(axis, False)


class _StubPeripheralManager:
    def __init__(
        self,
        *,
        switch_state: SwitchState | None = None,
        gamepad: _StubGamepad | None = None,
    ) -> None:
        self._switch_state = switch_state or SwitchState(0, 0, 0, 0, 0)
        self._gamepad = gamepad
        self.subscribers: list = []

    def get_main_switch_state(self) -> SwitchState:
        return self._switch_state

    def subscribe_main_switch(self, handler):
        self.subscribers.append(handler)
        handler(self._switch_state)
        return lambda: None

    def get_gamepad(self):
        if self._gamepad is None:
            raise ValueError("No gamepad available")
        return self._gamepad


@pytest.fixture(autouse=True)
def init_pygame() -> None:
    pygame.init()
    yield
    pygame.quit()


@pytest.fixture
def frame_data() -> list[FrameDescription]:
    return [
        FrameDescription(
            frame=BoundingBox(x=i * 64, y=0, w=64, h=64),
            spriteSourceSize=BoundingBox(x=0, y=0, w=64, h=64),
            sourceSize=Size(w=64, h=64),
            duration=100,
            rotated=False,
            trimmed=False,
        )
        for i in range(3)
    ]


@pytest.fixture
def window() -> pygame.Surface:
    return pygame.Surface((128, 128), pygame.SRCALPHA)


@pytest.fixture
def orientation() -> Rectangle:
    return Rectangle.with_layout(1, 1)


def test_boomerang_loop_stays_bounded(monkeypatch: pytest.MonkeyPatch, frame_data: list[FrameDescription], window: pygame.Surface, orientation: Rectangle) -> None:
    manager = _StubPeripheralManager()
    spritesheet = _StubSpritesheet()
    monkeypatch.setattr(assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet)

    clock = _StubClock(0, *([150] * 20))
    renderer = SpritesheetLoop(
        "irrelevant.png",
        disable_input=True,
        boomerang=True,
        frame_data=frame_data,
    )
    renderer.initialize(window, clock, manager, orientation)
    renderer.update_state(time_since_last_update=frame_data[0].duration + 1)

    history = []
    for _ in range(15):
        renderer.process(window, clock, manager, orientation)
        history.append(renderer.state)

    assert all(0 <= state.current_frame < len(frame_data) for state in history)
    assert any(state.reverse_direction for state in history)
    assert history[-1].loop_count == 0
    assert history[-1].phase == LoopPhase.LOOP


def test_reset_preserves_loaded_resources(monkeypatch: pytest.MonkeyPatch, frame_data: list[FrameDescription], window: pygame.Surface, orientation: Rectangle) -> None:
    gamepad = _StubGamepad()
    manager = _StubPeripheralManager(gamepad=gamepad)
    spritesheet = _StubSpritesheet()
    monkeypatch.setattr(assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet)

    renderer = SpritesheetLoop(
        "irrelevant.png",
        disable_input=False,
        boomerang=False,
        frame_data=frame_data,
    )
    renderer.initialize(window, _StubClock(0), manager, orientation)

    renderer.update_state(
        current_frame=2,
        loop_count=3,
        phase=LoopPhase.END,
        duration_scale=0.5,
        time_since_last_update=123,
    )

    renderer.reset()
    state = renderer.state

    assert state.spritesheet is not None
    assert state.gamepad is gamepad
    assert state.current_frame == 0
    assert state.loop_count == 0
    assert state.phase == LoopPhase.LOOP
    assert state.duration_scale == pytest.approx(0.0)
    assert state.time_since_last_update is None


def test_on_switch_state_updates_duration(monkeypatch: pytest.MonkeyPatch, frame_data: list[FrameDescription], window: pygame.Surface, orientation: Rectangle) -> None:
    gamepad = _StubGamepad()
    manager = _StubPeripheralManager(gamepad=gamepad)
    spritesheet = _StubSpritesheet()
    monkeypatch.setattr(assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet)

    renderer = SpritesheetLoop(
        "irrelevant.png",
        disable_input=False,
        boomerang=False,
        frame_data=frame_data,
    )
    renderer.initialize(window, _StubClock(0), manager, orientation)

    renderer.on_switch_state(SwitchState(0, 0, 0, 10, 0))
    renderer.on_switch_state(SwitchState(0, 0, 0, 25, 0))
    state_after_increase = renderer.state
    assert state_after_increase.duration_scale == pytest.approx(0.10)
    assert state_after_increase.last_switch_rotation == 25

    renderer.on_switch_state(SwitchState(0, 0, 0, 5, 0))
    state_after_decrease = renderer.state
    assert state_after_decrease.duration_scale == pytest.approx(0.05)
    assert state_after_decrease.last_switch_rotation == 5


def test_switch_state_ignored_when_input_disabled(monkeypatch: pytest.MonkeyPatch, frame_data: list[FrameDescription], window: pygame.Surface, orientation: Rectangle) -> None:
    manager = _StubPeripheralManager()
    spritesheet = _StubSpritesheet()
    monkeypatch.setattr(assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet)

    renderer = SpritesheetLoop(
        "irrelevant.png",
        disable_input=True,
        boomerang=False,
        frame_data=frame_data,
    )
    renderer.initialize(window, _StubClock(0), manager, orientation)

    initial_state = renderer.state
    renderer.on_switch_state(SwitchState(0, 0, 0, 10, 0))
    assert renderer.state == initial_state

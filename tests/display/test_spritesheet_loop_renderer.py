"""Validate spritesheet loop state updates from provider streams."""

import pygame
import pytest
from reactivex.subject import BehaviorSubject

from heart.assets import loader as assets_loader
from heart.device import Rectangle
from heart.peripheral.switch import SwitchState
from heart.renderers.spritesheet import (BoundingBox, FrameDescription,
                                         LoopPhase, Size, SpritesheetLoop)


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

    def image_at_scaled(
        self, rect: tuple[int, int, int, int], size: tuple[int, int]
    ) -> pygame.Surface:
        image = self.image_at(rect)
        return pygame.transform.scale(image, size)


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
        self._switch_stream = BehaviorSubject(self._switch_state)
        self.game_tick = BehaviorSubject(None)
        self.clock = BehaviorSubject(None)

    def get_main_switch_subscription(self):
        return self._switch_stream

    def get_gamepad(self):
        if self._gamepad is None:
            raise ValueError("No gamepad available")
        return self._gamepad


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


class TestSpritesheetLoopProvider:
    """Validate spritesheet loop state updates sourced from provider streams."""

    def test_boomerang_loop_stays_bounded(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: pygame.Surface,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Ensure boomerang loops stay within frame bounds so animations remain stable."""

        manager = _StubPeripheralManager()
        spritesheet = _StubSpritesheet()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        clock = stub_clock_factory(0, *([150] * 20))
        manager.clock.on_next(clock)
        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=True,
            boomerang=True,
            frame_data=frame_data,
        )
        renderer.initialize(window, clock, manager, orientation)

        history = []
        for _ in range(15):
            manager.game_tick.on_next(True)
            history.append(renderer.state)

        assert all(0 <= state.current_frame < len(frame_data) for state in history)
        assert any(state.reverse_direction for state in history)
        assert history[-1].loop_count == 0
        assert history[-1].phase == LoopPhase.LOOP

    def test_reset_preserves_loaded_resources(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: pygame.Surface,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Confirm reset/reinitialize cycles keep spritesheet assets attached for continuity."""

        gamepad = _StubGamepad()
        manager = _StubPeripheralManager(gamepad=gamepad)
        spritesheet = _StubSpritesheet()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        clock = stub_clock_factory(0)
        manager.clock.on_next(clock)
        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=False,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, clock, manager, orientation)
        manager.game_tick.on_next(True)

        renderer.reset()
        manager.clock.on_next(None)
        renderer.initialize(window, clock, manager, orientation)

        state = renderer.state

        assert state.spritesheet is spritesheet
        assert state.gamepad is gamepad
        assert state.current_frame == 0
        assert state.loop_count == 0
        assert state.phase == LoopPhase.LOOP
        assert state.duration_scale == pytest.approx(0.0)
        assert state.time_since_last_update is None

    def test_on_switch_state_updates_duration(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: pygame.Surface,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Verify switch rotation updates duration scaling to keep input-driven pacing responsive."""

        gamepad = _StubGamepad()
        manager = _StubPeripheralManager(gamepad=gamepad)
        spritesheet = _StubSpritesheet()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        clock = stub_clock_factory(0)
        manager.clock.on_next(clock)
        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=False,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, clock, manager, orientation)

        manager.get_main_switch_subscription().on_next(SwitchState(0, 0, 0, 10, 0))
        manager.get_main_switch_subscription().on_next(SwitchState(0, 0, 0, 25, 0))

        state_after_increase = renderer.state
        assert state_after_increase.duration_scale == pytest.approx(0.10)
        assert state_after_increase.last_switch_rotation == 25

        manager.get_main_switch_subscription().on_next(SwitchState(0, 0, 0, 5, 0))
        state_after_decrease = renderer.state
        assert state_after_decrease.duration_scale == pytest.approx(0.05)
        assert state_after_decrease.last_switch_rotation == 5

    def test_switch_state_ignored_when_input_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: pygame.Surface,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Ensure switch events do not mutate state when input handling is disabled."""

        manager = _StubPeripheralManager()
        spritesheet = _StubSpritesheet()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        clock = stub_clock_factory(0)
        manager.clock.on_next(clock)
        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=True,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, clock, manager, orientation)

        initial_state = renderer.state
        manager.get_main_switch_subscription().on_next(SwitchState(0, 0, 0, 10, 0))
        assert renderer.state == initial_state

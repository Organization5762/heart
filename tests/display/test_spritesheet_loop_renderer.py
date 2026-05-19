"""Validate spritesheet loop state updates from provider streams."""

import pygame
import pytest
from manyfold import BehaviorSubject

from heart.assets import loader as assets_loader
from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.switch import SwitchState
from heart.renderers.spritesheet import (BoundingBox, FrameDescription,
                                         LoopPhase, Size, SpritesheetLoop)
from heart.runtime.display_context import DisplayContext


class _SpriteSheetProbe:
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


def _peripheral_manager(
    monkeypatch: pytest.MonkeyPatch,
    *,
    gamepad: Gamepad | None = None,
) -> tuple[PeripheralManager, BehaviorSubject[SwitchState]]:
    manager = PeripheralManager()
    switch_stream = BehaviorSubject(SwitchState(0, 0, 0, 0, 0))
    monkeypatch.setattr(manager.input_io, "main_switch_stream", lambda: switch_stream)
    if gamepad is not None:
        manager.register(gamepad)
    return manager, switch_stream


def _advance_frame(
    manager: PeripheralManager, clock_factory, *, delta_ms: float
) -> None:
    manager.input_io.frame_ticks.advance(clock_factory(int(delta_ms)))


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
        window: DisplayContext,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Ensure boomerang loops stay within frame bounds so animations remain stable."""

        manager, _ = _peripheral_manager(monkeypatch)
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=True,
            boomerang=True,
            frame_data=frame_data,
        )
        renderer.initialize(window, manager, orientation)

        history = []
        for _ in range(15):
            _advance_frame(manager, stub_clock_factory, delta_ms=150.0)
            history.append(renderer.state)

        assert all(0 <= state.current_frame < len(frame_data) for state in history)
        assert any(state.reverse_direction for state in history)
        assert history[-1].loop_count == 0
        assert history[-1].phase == LoopPhase.LOOP

    def test_reset_preserves_loaded_resources(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: DisplayContext,
        orientation: Rectangle,
        stub_clock_factory,
    ) -> None:
        """Confirm reset/reinitialize cycles keep spritesheet assets attached for continuity."""

        gamepad = Gamepad()
        manager, _ = _peripheral_manager(monkeypatch, gamepad=gamepad)
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=False,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, manager, orientation)
        _advance_frame(manager, stub_clock_factory, delta_ms=0.0)

        renderer.reset()
        renderer.initialize(window, manager, orientation)

        state = renderer.state

        assert state.spritesheet is spritesheet
        assert state.gamepad is gamepad
        assert state.current_frame == 1
        assert state.loop_count == 0
        assert state.phase == LoopPhase.LOOP
        assert state.duration_scale == pytest.approx(0.0)
        assert state.time_since_last_update == 0

    def test_on_switch_state_updates_duration(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: DisplayContext,
        orientation: Rectangle,
    ) -> None:
        """Verify switch rotation updates duration scaling to keep input-driven pacing responsive."""

        gamepad = Gamepad()
        manager, switch_stream = _peripheral_manager(monkeypatch, gamepad=gamepad)
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=False,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, manager, orientation)

        switch_stream.on_next(SwitchState(0, 0, 0, 10, 0))
        switch_stream.on_next(SwitchState(0, 0, 0, 25, 0))

        state_after_increase = renderer.state
        assert state_after_increase.duration_scale == pytest.approx(0.10)
        assert state_after_increase.last_switch_rotation == 25

        switch_stream.on_next(SwitchState(0, 0, 0, 5, 0))
        state_after_decrease = renderer.state
        assert state_after_decrease.duration_scale == pytest.approx(0.05)
        assert state_after_decrease.last_switch_rotation == 5

    def test_switch_state_ignored_when_input_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        frame_data: list[FrameDescription],
        window: DisplayContext,
        orientation: Rectangle,
    ) -> None:
        """Ensure switch events do not mutate state when input handling is disabled."""

        manager, switch_stream = _peripheral_manager(monkeypatch)
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            assets_loader.Loader, "load_spirtesheet", lambda path: spritesheet
        )

        renderer = SpritesheetLoop(
            "irrelevant.png",
            disable_input=True,
            boomerang=False,
            frame_data=frame_data,
        )
        renderer.initialize(window, manager, orientation)

        initial_state = renderer.state
        switch_stream.on_next(SwitchState(0, 0, 0, 10, 0))
        assert renderer.state == initial_state

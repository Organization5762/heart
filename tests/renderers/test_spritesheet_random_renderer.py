"""Validate random spritesheet renderer sizing behavior."""

from __future__ import annotations

import pygame

from heart.device import Device
from heart.renderers.spritesheet_random.renderer import SpritesheetLoopRandom
from heart.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)
from heart.runtime.display_context import DisplayContext


class _StubSpritesheet:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[int, int, int, int], tuple[int, int]]] = []

    def image_at_scaled(
        self,
        rect: tuple[int, int, int, int],
        size: tuple[int, int],
    ) -> pygame.Surface:
        self.calls.append((rect, size))
        return pygame.Surface(size, pygame.SRCALPHA)


class _StubProvider:
    def __init__(self) -> None:
        frame = type("Frame", (), {"frame": (0, 0, 64, 64)})()
        self.frames = {phase: [frame] for phase in LoopPhase}


class TestSpritesheetLoopRandom:
    """Ensure random spritesheet rendering stays correctly scaled so fullscreen effects do not regress into single-panel output."""

    def test_real_process_scales_full_window_when_enabled(
        self,
        device: Device,
    ) -> None:
        """Verify fill-window spritesheets use the active display size so fullscreen animations occupy the whole installation instead of one tile."""
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size(), pygame.SRCALPHA),
            clock=pygame.time.Clock(),
        )
        renderer = SpritesheetLoopRandom(
            screen_width=64,
            screen_height=64,
            screen_count=4,
            sheet_file_path="unused.png",
            metadata_file_path="unused.json",
            randomness=None,  # type: ignore[arg-type]
            fill_window=True,
            provider=_StubProvider(),
        )
        spritesheet = _StubSpritesheet()
        renderer.set_state(
            SpritesheetLoopRandomState(
                switch_state=None,
                spritesheet=spritesheet,
                phase=LoopPhase.LOOP,
            )
        )

        renderer.real_process(window, device.orientation)

        assert spritesheet.calls == [((0, 0, 64, 64), window.get_size())]

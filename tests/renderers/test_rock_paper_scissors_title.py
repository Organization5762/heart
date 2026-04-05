"""Regression tests for the rock-paper-scissors title renderer."""

from __future__ import annotations

import time

import pygame

from heart.device import Device
from heart.renderers.rock_paper_scissors.state import (
    RockPaperScissorsPhase,
    RockPaperScissorsState,
)
from heart.renderers.rock_paper_scissors.title import RockPaperScissorsTitle
from heart.runtime.display_context import DisplayContext


class TestRockPaperScissorsTitle:
    """Ensure the title renderer paints a fresh frame each tick."""

    def test_real_process_clears_previous_frame_before_blitting(
        self,
        device: Device,
        monkeypatch,
    ) -> None:
        """Verify the title screen clears stale pixels so prior mode artwork does not bleed through around the centered throw image."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size(), pygame.SRCALPHA),
            clock=pygame.time.Clock(),
        )
        assert window.screen is not None
        window.screen.fill((255, 0, 0))

        renderer = RockPaperScissorsTitle()
        renderer.set_state(
            RockPaperScissorsState(
                phase=RockPaperScissorsPhase.REVEAL,
                phase_started_at=0.0,
                selected_throw="rock",
            )
        )
        renderer._last_frame_time = time.monotonic()
        renderer._images["rock"] = pygame.Surface((16, 16), pygame.SRCALPHA)
        renderer._images["rock"].fill((255, 255, 255, 255))
        monkeypatch.setattr(renderer, "_ensure_assets_loaded", lambda _window: None)

        renderer.real_process(window, device.orientation)

        assert window.screen.get_at((0, 0))[:3] == (0, 0, 0)

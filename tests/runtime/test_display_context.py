"""Validate display-context mode switching so OpenGL transitions stay recoverable."""

from __future__ import annotations

from unittest.mock import Mock

import pygame
import pytest

from heart import DeviceDisplayMode
from heart.runtime.display_context import DisplayContext


class TestDisplayContext:
    """Ensure display-mode transitions are explicit and reversible so renderer failures do not strand the runtime in the wrong pygame mode."""

    def test_display_mode_restores_previous_mode_after_failure(
        self,
        device,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify the mode context restores the previous display mode on errors so failed OpenGL renders do not leave later scenes with a mismatched display."""
        display_context = DisplayContext(device=device)
        display_context.last_render_mode = DeviceDisplayMode.FULL.to_pygame_mode()
        display_context.screen = pygame.Surface(device.scaled_display_size())

        set_mode_calls: list[int] = []

        def _fake_set_mode(_size: tuple[int, int], flags: int) -> pygame.Surface:
            set_mode_calls.append(flags)
            return pygame.Surface(device.scaled_display_size())

        monkeypatch.setattr(pygame.display, "init", lambda: None)
        monkeypatch.setattr(pygame.display, "set_mode", _fake_set_mode)
        device.set_screen = Mock()

        with pytest.raises(RuntimeError, match="boom"):
            with display_context.display_mode(DeviceDisplayMode.OPENGL):
                raise RuntimeError("boom")

        assert set_mode_calls == [
            DeviceDisplayMode.OPENGL.to_pygame_mode(),
            DeviceDisplayMode.FULL.to_pygame_mode(),
        ]
        assert display_context.last_render_mode == DeviceDisplayMode.FULL.to_pygame_mode()

    def test_scratch_context_rejects_mode_switching(self, device) -> None:
        """Verify scratch contexts cannot call set_mode so per-renderer surfaces never mutate the real pygame display behind the game loop."""
        display_context = DisplayContext(
            device=device,
            screen=pygame.Surface(device.scaled_display_size()),
        )
        scratch = display_context.create_scratch_context(
            orientation=device.orientation,
            display_mode=DeviceDisplayMode.MIRRORED,
        )

        with pytest.raises(
            RuntimeError,
            match="Scratch DisplayContext instances cannot change display modes",
        ):
            with scratch.display_mode(DeviceDisplayMode.OPENGL):
                pass

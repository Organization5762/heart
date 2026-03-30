"""Validate text renderer layout and multiline spacing."""

from __future__ import annotations

import pygame

from heart.device import Device
from heart.display.color import Color
from heart.renderers.text.renderer import TextRendering
from heart.renderers.text.state import TextRenderingState
from heart.runtime.display_context import DisplayContext


class _StubFont:
    def __init__(self, width: int = 6, height: int = 4, line_height: int = 7) -> None:
        self._width = width
        self._height = height
        self._line_height = line_height

    def render(
        self,
        text: str,
        antialias: bool,
        color: tuple[int, int, int],
    ) -> pygame.Surface:
        surface = pygame.Surface((self._width, self._height))
        surface.fill(color)
        return surface

    def get_linesize(self) -> int:
        return self._line_height


class TestTextRendering:
    """Ensure text rendering keeps multiline layout readable so text-only modes remain legible on-device."""

    def test_real_process_offsets_each_line_vertically(
        self,
        device: Device,
    ) -> None:
        """Verify multiline text advances by line height so stacked messages render as separate rows rather than overlapping into one unreadable block."""
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = TextRendering(
            text=["Where's\nmy\nfriends"],
            font="stub",
            font_size=14,
            color=Color(255, 255, 255),
            x_location=0,
            y_location=0,
        )
        renderer.set_state(
            TextRenderingState(
                switch_state=None,
                text=("Where's\nmy\nfriends",),
                font_name="stub",
                font_size=14,
                color=Color(255, 255, 255),
                x_location=0,
                y_location=0,
            )
        )
        renderer._font = _StubFont()
        renderer._font_key = ("stub", 14)

        renderer.real_process(window, device.orientation)

        assert window.screen is not None
        occupied_rows = [
            row
            for row in range(window.screen.get_height())
            if any(
                window.screen.get_at((column, row))[:3] != (0, 0, 0)
                for column in range(window.screen.get_width())
            )
        ]

        assert occupied_rows == [0, 1, 2, 3, 7, 8, 9, 10, 14, 15, 16, 17]

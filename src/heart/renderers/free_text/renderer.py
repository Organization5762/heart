from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.free_text.provider import (TEXT_PADDING_PX,
                                                FreeTextStateProvider)
from heart.renderers.free_text.state import FreeTextRendererState
from heart.runtime.display_context import DisplayContext

TEXT_COLOR = (255, 105, 180)
TEXT_ANTIALIAS = False


class FreeTextRenderer(StatefulBaseRenderer[FreeTextRendererState]):
    """Render the most recent text message that arrived via *PhoneText*."""

    def __init__(self, provider: FreeTextStateProvider | None = None) -> None:
        self._provider = provider or FreeTextStateProvider()
        self._cached_text: str | None = None
        self._cached_window_size: tuple[int, int] | None = None
        self._cached_font: pygame.font.Font | None = None
        self._cached_wrapped_lines: tuple[str, ...] = tuple()
        self._cached_line_height = 0
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def set_text(self, text: str) -> None:
        if self._provider is not None:
            self._provider.set_text(text)

    def _current_font(self, state: FreeTextRendererState) -> pygame.font.Font:
        return self._provider.get_font(state.font_size)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        if not state.text:
            return

        window_width, window_height = window.get_size()
        font, wrapped_lines, line_height = self._layout_text(
            text=state.text,
            window_width=window_width,
            window_height=window_height,
        )
        if not wrapped_lines:
            return

        available_width = max(1, window_width - (TEXT_PADDING_PX * 2))
        available_height = max(1, window_height - (TEXT_PADDING_PX * 2))
        max_lines_visible = max(1, available_height // line_height)
        visible_lines = list(wrapped_lines[:max_lines_visible])

        total_height = len(visible_lines) * line_height
        y = TEXT_PADDING_PX + max(0, (available_height - total_height) // 2)

        for line in visible_lines:
            rendered = font.render(line, TEXT_ANTIALIAS, TEXT_COLOR)
            text_width, _ = rendered.get_size()
            x = TEXT_PADDING_PX + max(0, (available_width - text_width) // 2)
            window.blit(rendered, (x, y))
            y += line_height

    def _layout_text(
        self,
        *,
        text: str,
        window_width: int,
        window_height: int,
    ) -> tuple[pygame.font.Font, tuple[str, ...], int]:
        window_size = (window_width, window_height)
        if (
            self._cached_text != text
            or self._cached_window_size != window_size
            or self._cached_font is None
        ):
            font, wrapped_lines, line_height = self._provider.fit_text_to_window(
                text=text,
                window_width=window_width,
                window_height=window_height,
            )
            self._cached_text = text
            self._cached_window_size = window_size
            self._cached_font = font
            self._cached_wrapped_lines = wrapped_lines
            self._cached_line_height = line_height

        assert self._cached_font is not None
        return self._cached_font, self._cached_wrapped_lines, self._cached_line_height

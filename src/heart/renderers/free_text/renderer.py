from __future__ import annotations

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.free_text.provider import FreeTextStateProvider
from heart.renderers.free_text.state import FreeTextRendererState
from heart.runtime.display_context import DisplayContext

TEXT_COLOR = (255, 105, 180)
TEXT_ANTIALIAS = False


class FreeTextRenderer(StatefulBaseRenderer[FreeTextRendererState]):
    """Render the most recent text message that arrived via *PhoneText*."""

    def __init__(self, provider: FreeTextStateProvider | None = None) -> None:
        self._provider = provider or FreeTextStateProvider()
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[FreeTextRendererState]:
        return self._provider.observable(peripheral_manager)

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

        font = self._current_font(state)
        window_width, window_height = window.get_size()

        if not state.wrapped_lines:
            return

        line_height = state.line_height or font.get_linesize()
        max_lines_visible = max(1, window_height // line_height)
        visible_lines = list(state.wrapped_lines[:max_lines_visible])

        total_height = len(visible_lines) * line_height
        y = (window_height - total_height) // 2

        for line in visible_lines:
            rendered = font.render(line, TEXT_ANTIALIAS, TEXT_COLOR)
            text_width, _ = rendered.get_size()
            x = (window_width - text_width) // 2
            window.blit(rendered, (x, y))
            y += line_height

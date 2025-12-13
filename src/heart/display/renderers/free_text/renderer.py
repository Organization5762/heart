from __future__ import annotations

import pygame
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.free_text.provider import FreeTextStateProvider
from heart.display.renderers.free_text.state import FreeTextRendererState
from heart.peripheral.core.manager import PeripheralManager


class FreeTextRenderer(AtomicBaseRenderer[FreeTextRendererState]):
    """Render the most recent text message that arrived via *PhoneText*."""

    def __init__(self) -> None:
        self._provider: FreeTextStateProvider | None = None
        self._subscription: Disposable | None = None
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def reset(self) -> None:
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None
        super().reset()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FreeTextRendererState:
        self._provider = FreeTextStateProvider(peripheral_manager)
        initial_state = self._provider.initial_state()
        self.set_state(initial_state)
        self._subscription = self._provider.observable().subscribe(on_next=self.set_state)
        return initial_state

    def set_text(self, text: str) -> None:
        if self._provider is not None:
            self._provider.set_text(text)

    def _current_font(self, state: FreeTextRendererState) -> pygame.font.Font:
        assert self._provider is not None
        return self._provider.get_font(state.font_size)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
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
            rendered = font.render(line, True, (255, 105, 180))
            text_width, _ = rendered.get_size()
            x = (window_width - text_width) // 2
            window.blit(rendered, (x, y))
            y += line_height

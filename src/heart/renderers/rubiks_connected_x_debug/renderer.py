from __future__ import annotations

import pygame

from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.rubiks_connected_x_debug.provider import \
    RubiksConnectedXDebugStateProvider
from heart.renderers.rubiks_connected_x_debug.state import \
    RubiksConnectedXDebugState
from heart.runtime.display_context import DisplayContext

DEFAULT_MARGIN_PX = 10
DEFAULT_LINE_SPACING_PX = 4
DEFAULT_FONT_SIZE_PX = 18
TEXT_COLOR = (240, 240, 240)


class RubiksConnectedXDebugRenderer(StatefulBaseRenderer[RubiksConnectedXDebugState]):
    """Draw the latest raw cube notification on screen for protocol debugging."""

    def __init__(
        self,
        provider: RubiksConnectedXDebugStateProvider | None = None,
    ) -> None:
        self._font: pygame.font.Font | None = None
        super().__init__(builder=provider or RubiksConnectedXDebugStateProvider())

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if not pygame.font.get_init():
            pygame.font.init()
        if self._font is None:
            self._font = pygame.font.Font(None, DEFAULT_FONT_SIZE_PX)
        font = self._font
        y_offset = DEFAULT_MARGIN_PX
        for line in self.state.status_lines:
            text_surface = font.render(line, True, TEXT_COLOR)
            window.screen.blit(text_surface, (DEFAULT_MARGIN_PX, y_offset))
            y_offset += text_surface.get_height() + DEFAULT_LINE_SPACING_PX

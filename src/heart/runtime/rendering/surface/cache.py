from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from heart.runtime.display_context import DisplayContext

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer


class RendererSurfaceCache:
    def __init__(self, display_context: DisplayContext) -> None:
        self._display_context = display_context

    def get(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        # TODO: Kind don't want to return back the base, real screen
        return self._display_context.screen

        # self._display_context.get_size()
        # return pygame.Surface(self._display_context.get_size(), pygame.SRCALPHA)

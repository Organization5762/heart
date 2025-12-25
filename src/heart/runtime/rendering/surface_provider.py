from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from heart.device import Device
from heart.runtime.rendering.display import DisplayModeManager
from heart.runtime.rendering.surface_cache import RendererSurfaceCache

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


class RendererSurfaceProvider:
    def __init__(
        self,
        device: Device,
        display_manager: DisplayModeManager | None = None,
        surface_cache: RendererSurfaceCache | None = None,
    ) -> None:
        self._display_manager = display_manager or DisplayModeManager(device)
        self._surface_cache = surface_cache or RendererSurfaceCache(device)

    def prepare(self, renderer: "StatefulBaseRenderer[Any]") -> pygame.Surface:
        self._display_manager.ensure_mode(renderer.device_display_mode)
        return self._surface_cache.get(renderer)

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer


class RendererSurfaceCache:
    def __init__(self, device: Device) -> None:
        self._device = device
        self._renderer_surface_cache: dict[
            tuple[int, DeviceDisplayMode, tuple[int, int]], pygame.Surface
        ] = {}

    def get_surface(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        size = self._device.full_display_size()
        if not Configuration.render_screen_cache_enabled():
            return pygame.Surface(size, pygame.SRCALPHA)

        cache_key = (id(renderer), renderer.device_display_mode, size)
        cached = self._renderer_surface_cache.get(cache_key)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._renderer_surface_cache[cache_key] = cached
        else:
            cached.fill((0, 0, 0, 0))
        return cached

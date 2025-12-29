from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pygame

from heart.device import Device

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer


class RendererSurfaceCache:
    def __init__(self, device: Device) -> None:
        self._device = device

    def get(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        size = self._device.full_display_size()
        return pygame.Surface(size, pygame.SRCALPHA)
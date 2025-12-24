from __future__ import annotations

import pygame

from heart.renderers.internal import FrameAccumulator
from heart.utilities.env import Configuration


class SurfaceComposer:
    def __init__(self) -> None:
        self._composite_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._composite_accumulator: FrameAccumulator | None = None

    def compose_batched(self, surfaces: list[pygame.Surface]) -> pygame.Surface:
        size = surfaces[0].get_size()
        composite = self._get_composite_surface(size)
        accumulator = self._get_composite_accumulator(composite)
        for surface in surfaces:
            accumulator.queue_blit(surface)
        return accumulator.flush(clear=False)

    def _get_composite_surface(self, size: tuple[int, int]) -> pygame.Surface:
        if not Configuration.render_screen_cache_enabled():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            return surface

        cached = self._composite_surface_cache.get(size)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._composite_surface_cache[size] = cached
        cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_accumulator(
        self, surface: pygame.Surface
    ) -> FrameAccumulator:
        if (
            self._composite_accumulator is None
            or self._composite_accumulator.surface is not surface
        ):
            self._composite_accumulator = FrameAccumulator(surface)
        else:
            self._composite_accumulator.reset()
        return self._composite_accumulator

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import pygame

from heart.runtime.rendering.composition import SurfaceComposer
from heart.utilities.env import Configuration, RenderMergeStrategy


class SurfaceMerger:
    def __init__(
        self,
        merge_pair: Callable[[pygame.Surface, pygame.Surface], pygame.Surface],
        *,
        composer: SurfaceComposer | None = None,
    ) -> None:
        self._merge_pair = merge_pair
        self._composer = composer or SurfaceComposer()

    def merge_surfaces_serial(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = surfaces[0]
            for surface in surfaces[1:]:
                base = self._merge_pair(base, surface)
            return base
        return self._composer.compose_batched(surfaces)

    def merge_surfaces_parallel(
        self,
        surfaces: list[pygame.Surface],
        executor: ThreadPoolExecutor,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED:
            return self._composer.compose_batched(surfaces)
        return self._merge_surfaces_parallel(surfaces, executor)

    def _merge_surface_pair(
        self, surfaces: tuple[pygame.Surface, pygame.Surface]
    ) -> pygame.Surface:
        return self._merge_pair(*surfaces)

    def _merge_surfaces_parallel(
        self,
        surfaces: list[pygame.Surface],
        executor: ThreadPoolExecutor,
    ) -> pygame.Surface:
        while len(surfaces) > 1:
            pairs = list(zip(surfaces[0::2], surfaces[1::2]))

            merged_surfaces = list(executor.map(self._merge_surface_pair, pairs))

            if len(surfaces) % 2 == 1:
                merged_surfaces.append(surfaces[-1])

            surfaces = merged_surfaces
        return surfaces[0]

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pygame

from heart.runtime.rendering.composition import SurfaceComposer
from heart.utilities.env import Configuration, RenderMergeStrategy


class SurfaceMerger:
    def __init__(self, composer: SurfaceComposer | None = None) -> None:
        self._composer = composer or SurfaceComposer()

    def merge_in_place(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def compose(self, surfaces: list[pygame.Surface]) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = surfaces[0]
            for surface in surfaces[1:]:
                base = self.merge_in_place(base, surface)
            return base
        return self._composer.compose_batched(surfaces)

    def merge_parallel(
        self,
        surfaces: list[pygame.Surface],
        executor: ThreadPoolExecutor,
        merge_fn: Callable[[pygame.Surface, pygame.Surface], pygame.Surface] | None = None,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED:
            return self._composer.compose_batched(surfaces)
        return self._merge_surfaces_parallel(
            surfaces, executor, merge_fn or self.merge_in_place
        )

    def _merge_surface_pair(
        self,
        surfaces: tuple[pygame.Surface, pygame.Surface],
        merge_fn: Callable[[pygame.Surface, pygame.Surface], pygame.Surface],
    ) -> pygame.Surface:
        return merge_fn(*surfaces)

    def _merge_surfaces_parallel(
        self,
        surfaces: list[pygame.Surface],
        executor: ThreadPoolExecutor,
        merge_fn: Callable[[pygame.Surface, pygame.Surface], pygame.Surface],
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        while len(surfaces) > 1:
            pairs = list(zip(surfaces[0::2], surfaces[1::2]))
            merge_pair = partial(self._merge_surface_pair, merge_fn=merge_fn)
            merged_surfaces = list(executor.map(merge_pair, pairs))
            if len(surfaces) % 2 == 1:
                merged_surfaces.append(surfaces[-1])
            surfaces = merged_surfaces
        return surfaces[0]

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import pygame

from heart.runtime.rendering.composition import SurfaceComposer
from heart.utilities.env import Configuration, RenderMergeStrategy


class SurfaceCompositionManager:
    def __init__(
        self,
        composer: SurfaceComposer | None = None,
        strategy_provider: Callable[[], RenderMergeStrategy] | None = None,
    ) -> None:
        self._composer = composer or SurfaceComposer()
        self._strategy_provider = strategy_provider or Configuration.render_merge_strategy

    def merge_in_place(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def compose_serial(
        self,
        surfaces: list[pygame.Surface],
        merge_fn: Callable[[pygame.Surface, pygame.Surface], pygame.Surface] | None = None,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if self._strategy_provider() == RenderMergeStrategy.IN_PLACE:
            base = surfaces[0]
            merge_surfaces = merge_fn or self.merge_in_place
            for surface in surfaces[1:]:
                base = merge_surfaces(base, surface)
            return base
        return self._composer.compose_batched(surfaces)

    def compose_parallel(
        self,
        surfaces: list[pygame.Surface],
        executor: ThreadPoolExecutor,
        merge_fn: Callable[[pygame.Surface, pygame.Surface], pygame.Surface] | None = None,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if self._strategy_provider() == RenderMergeStrategy.BATCHED:
            return self._composer.compose_batched(surfaces)
        merge_surfaces = merge_fn or self.merge_in_place
        return self._merge_surfaces_parallel(surfaces, executor, merge_surfaces)

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

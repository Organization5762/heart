from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Sequence

import pygame

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

RenderSurfaceCallback = Callable[["StatefulBaseRenderer[Any]"], pygame.Surface | None]


class RenderSurfaceCollector:
    def __init__(
        self,
        process_renderer: RenderSurfaceCallback,
        executor_factory: Callable[[], ThreadPoolExecutor],
    ) -> None:
        self._process_renderer = process_renderer
        self._executor_factory = executor_factory

    def collect(
        self,
        renderers: Sequence["StatefulBaseRenderer[Any]"],
        *,
        parallel: bool,
    ) -> list[pygame.Surface]:
        if parallel:
            return self._collect_parallel(renderers)
        return self._collect_serial(renderers)

    def _collect_serial(
        self,
        renderers: Sequence["StatefulBaseRenderer[Any]"],
    ) -> list[pygame.Surface]:
        if not renderers:
            return []
        surfaces: list[pygame.Surface] = []
        for renderer in renderers:
            surface = self._process_renderer(renderer)
            if surface is not None:
                surfaces.append(surface)
        return surfaces

    def _collect_parallel(
        self,
        renderers: Sequence["StatefulBaseRenderer[Any]"],
    ) -> list[pygame.Surface]:
        if not renderers:
            return []
        executor = self._executor_factory()
        return [
            surface
            for surface in executor.map(self._process_renderer, renderers)
            if surface is not None
        ]

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

import pygame

from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface.collection import RenderSurfaceCollector
from heart.runtime.rendering.surface.merge import SurfaceCompositionManager
from heart.runtime.rendering.variants import RendererVariant
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


@dataclass(frozen=True)
class RenderResult:
    surface: pygame.Surface | None


class RenderPipeline:
    def __init__(
        self,
        display_context: DisplayContext,
        peripheral_manager: PeripheralManager,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.display_context = display_context
        self.peripheral_manager = peripheral_manager
        self.renderer_variant = render_variant
        self.clock: pygame.time.Clock | None = None
        self._renderer_processor = RendererProcessor(display_context, peripheral_manager)
        self._timing_tracker = self._renderer_processor.timing_tracker
        self._composition_manager = SurfaceCompositionManager(
            strategy_provider=Configuration.render_merge_strategy()
        )
        self._surface_collector = RenderSurfaceCollector(
            lambda renderer: self.process_renderer(renderer),
            self._get_render_executor,
        )
        self._render_surface_iterative = self._render_surface_iterative_impl
        self._render_surfaces_binary = self._render_surfaces_binary_impl

        self._render_executor: ThreadPoolExecutor | None = None

    def render_with_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> RenderResult:
        render_fn = self._render_fn(renderers, None)
        return RenderResult(surface=render_fn(renderers))

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        return self._renderer_processor.process_renderer(renderer)

    def _should_collect_parallel(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        *,
        variant: RendererVariant | None = None,
    ) -> bool:
        resolved = variant or self.renderer_variant
        match resolved:
            case RendererVariant.ITERATIVE:
                return False
            case RendererVariant.BINARY:
                return True
            case RendererVariant.AUTO:
                if len(renderers) >= Configuration.render_parallel_threshold():
                    return True
                estimated_cost, has_samples = self._timing_tracker.estimate_total_ms(
                    renderers
                )
                return (
                    has_samples
                    and estimated_cost >= Configuration.render_parallel_cost_threshold_ms()
                )
            case _:
                return False

    def _render_surface_iterative_impl(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        surfaces = self._surface_collector.collect(renderers, parallel=False)
        return self._merge_surfaces_serial(surfaces)

    def _render_surfaces_binary_impl(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        surfaces = self._surface_collector.collect(renderers, parallel=True)
        return self._merge_surfaces_binary(surfaces)

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        variant: RendererVariant | None,
    ) -> Callable[[list["StatefulBaseRenderer[Any]"]], pygame.Surface | None]:
        resolved = variant or self.renderer_variant
        match resolved:
            case RendererVariant.BINARY:
                return self._render_surfaces_binary
            case RendererVariant.ITERATIVE:
                return self._render_surface_iterative
            case RendererVariant.AUTO:
                return (
                    self._render_surfaces_binary
                    if self._should_collect_parallel(renderers, variant=resolved)
                    else self._render_surface_iterative
                )
            case _:
                return self._render_surface_iterative

    ###
    # Other
    ###
    def set_clock(self, clock: pygame.time.Clock | None) -> None:
        self.clock = clock
        self._renderer_processor.set_clock(clock)

    def shutdown(self) -> None:
        if self._render_executor is not None:
            self._render_executor.shutdown(wait=True)
            self._render_executor = None

    def _get_render_executor(self) -> ThreadPoolExecutor:
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(
                max_workers=Configuration.render_executor_max_workers()
            )
        return self._render_executor

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        return self._composition_manager.merge_in_place(surface1, surface2)

    def _merge_surfaces_serial(
        self,
        surfaces: list[pygame.Surface],
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        base = surfaces[0]
        for surface in surfaces[1:]:
            base = self.merge_surfaces(base, surface)
        return base

    def _merge_surfaces_binary(
        self,
        surfaces: list[pygame.Surface],
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        working = list(surfaces)
        while len(working) > 1:
            merged: list[pygame.Surface] = []
            for index in range(0, len(working) - 1, 2):
                merged.append(self.merge_surfaces(working[index], working[index + 1]))
            if len(working) % 2 == 1:
                merged.append(working[-1])
            working = merged
        return working[0]

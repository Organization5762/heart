from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, assert_never

import pygame

from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.composition import SurfaceComposer
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.variants import RendererVariant
from heart.utilities.env import Configuration, RenderMergeStrategy

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


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
        self._merge_strategy = Configuration.render_merge_strategy()
        self._surface_composer = SurfaceComposer()
        self._render_surface_iterative = self._render_surface_iterative
        self._render_surfaces_binary = self._render_surfaces_binary
        self._render_executor: ThreadPoolExecutor | None = None

    def render(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        parallel = self._use_parallel_path(renderers)
        surfaces = self._collect_surfaces(renderers, parallel=parallel)
        return self._merge_surfaces(surfaces, pairwise=parallel)

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        return self._renderer_processor.process_renderer(renderer)

    def _use_parallel_path(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
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
                assert_never(resolved)

    def _collect_surfaces(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        *,
        parallel: bool,
    ) -> list[pygame.Surface]:
        if not renderers:
            return []
        if not parallel:
            surfaces: list[pygame.Surface] = []
            for renderer in renderers:
                surface = self.process_renderer(renderer)
                if surface is not None:
                    surfaces.append(surface)
            return surfaces

        executor = self._get_render_executor()
        return [
            surface
            for surface in executor.map(self.process_renderer, renderers)
            if surface is not None
        ]

        ###
    # Other
    ###
    def _render_surface_iterative(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        surfaces = self._collect_surfaces(renderers, parallel=False)
        if not surfaces:
            return None
        base = surfaces[0]
        for surface in surfaces[1:]:
            base = self.merge_surfaces(base, surface)
        return base

    def _render_surfaces_binary(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> pygame.Surface | None:
        surfaces = self._collect_surfaces(renderers, parallel=True)
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

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        variant: RendererVariant | None,
    ):
        resolved = variant or self.renderer_variant
        match resolved:
            case RendererVariant.BINARY:
                return self._render_surfaces_binary
            case RendererVariant.ITERATIVE:
                return self._render_surface_iterative
            case RendererVariant.AUTO:
                if self._use_parallel_path(renderers, variant=resolved):
                    return self._render_surfaces_binary
                return self._render_surface_iterative
            case _:
                assert_never(resolved)

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

    def _merge_surfaces(
        self,
        surfaces: list[pygame.Surface],
        *,
        pairwise: bool,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        match self._merge_strategy:
            case RenderMergeStrategy.IN_PLACE:
                return self._merge_surfaces_in_place(surfaces, pairwise=pairwise)
            case RenderMergeStrategy.BATCHED:
                return self._surface_composer.compose_batched(surfaces)
            case RenderMergeStrategy.ADAPTIVE:
                if len(surfaces) >= Configuration.render_merge_surface_threshold():
                    return self._surface_composer.compose_batched(surfaces)
                return self._merge_surfaces_in_place(surfaces, pairwise=pairwise)
            case _:
                assert_never(self._merge_strategy)

    def _merge_surfaces_in_place(
        self,
        surfaces: list[pygame.Surface],
        *,
        pairwise: bool,
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if not pairwise:
            base = surfaces[0]
            for surface in surfaces[1:]:
                base = self.merge_surfaces(base, surface)
            return base

        working = list(surfaces)
        while len(working) > 1:
            merged: list[pygame.Surface] = []
            for index in range(0, len(working) - 1, 2):
                merged.append(self.merge_surfaces(working[index], working[index + 1]))
            if len(working) % 2 == 1:
                merged.append(working[-1])
            working = merged
        return working[0]

    def merge_surfaces(
        self, base: pygame.Surface, overlay: pygame.Surface
    ) -> pygame.Surface:
        assert base.get_size() == overlay.get_size(), (
            "Surfaces must be the same size to merge."
        )
        base.blit(overlay, (0, 0))
        return base

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

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
            self._renderer_processor.process_renderer,
            self._get_render_executor
        )

        self._render_executor: ThreadPoolExecutor | None = None

    def render_with_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> RenderResult:
        surfaces = self._surface_collector.collect(renderers, parallel=False)
        surface = self._composition_manager.compose_serial(surfaces)
        return RenderResult(surface=surface)

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

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.plan import RenderPlan, RenderPlanner
from heart.runtime.rendering.plan.selector import RenderPlanSelector
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface.collection import RenderSurfaceCollector
from heart.runtime.rendering.surface.merge import SurfaceCompositionManager
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


@dataclass(frozen=True)
class RenderResult:
    surface: pygame.Surface | None
    plan: RenderPlan


class RenderPipeline:
    def __init__(
        self,
        device: Device,
        peripheral_manager: PeripheralManager,
        render_variant: RendererVariant = RendererVariant.ITERATIVE,
    ) -> None:
        self.device = device
        self.peripheral_manager = peripheral_manager
        self.renderer_variant = render_variant
        self.clock: pygame.time.Clock | None = None
        self._renderer_processor = RendererProcessor(device, peripheral_manager)
        self._timing_tracker = self._renderer_processor.timing_tracker
        self._planner = RenderPlanner(self._timing_tracker, render_variant)
        self._composition_manager = SurfaceCompositionManager(
            strategy_provider=self._planner.get_merge_strategy
        )
        self._surface_collector = RenderSurfaceCollector(
            self._renderer_processor.process_renderer,
            self._get_render_executor
        )

        self._render_dispatch: dict[RendererVariant, RenderMethod] = {
            RendererVariant.BINARY: self._render_surfaces_binary,
            RendererVariant.ITERATIVE: self._render_surface_iterative,
        }
        self._plan_selector = RenderPlanSelector(
            self._planner,
            self._render_dispatch,
        )
        self._render_executor: ThreadPoolExecutor | None = None

    def render_with_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderResult:
        plan = self._plan_selector.get_active_plan(
            renderers,
            self.renderer_variant,
            override_renderer_variant,
        )
        render_fn = self._plan_selector.resolve_render_method(plan)
        with self._plan_selector.activate_plan(plan):
            surface = render_fn(renderers)
        return RenderResult(surface=surface, plan=plan)

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

    def _render_surface_iterative(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        surfaces = self._surface_collector.collect(renderers, parallel=False)
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        surfaces = self._surface_collector.collect(renderers, parallel=True)

        # Set executor
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(
                max_workers=Configuration.render_executor_max_workers()
            )
        return self._composition_manager.compose_parallel(
            surfaces, self._render_executor, merge_fn=self.merge_surfaces
        )
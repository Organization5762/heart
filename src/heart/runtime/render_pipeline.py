from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.render_plan_cache import RenderPlanCache
from heart.runtime.render_planner import RenderPlan, RenderPlanner
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface_collection import RenderSurfaceCollector
from heart.runtime.rendering.surface_merge import SurfaceCompositionManager
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)


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
            self._process_renderer_delegate, self._get_render_executor
        )

        binary_method = cast(RenderMethod, self._render_surfaces_binary)
        iterative_method = cast(RenderMethod, self._render_surface_iterative)
        object.__setattr__(self, "_render_surfaces_binary", binary_method)
        object.__setattr__(self, "_render_surface_iterative", iterative_method)
        self._render_dispatch: dict[RendererVariant, RenderMethod] = {
            RendererVariant.BINARY: binary_method,
            RendererVariant.ITERATIVE: iterative_method,
        }
        self._render_executor: ThreadPoolExecutor | None = None
        self._active_plan: RenderPlan | None = None
        self._plan_cache = RenderPlanCache(
            self._planner,
            Configuration.render_plan_refresh_ms(),
            Configuration.render_plan_signature_strategy(),
        )

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

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        return self._renderer_processor.process_renderer(renderer)

    def _process_renderer_delegate(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        return self.process_renderer(renderer)

    def estimate_render_cost_ms(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> float | None:
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        if not has_samples:
            return None
        return estimated_cost_ms

    def finalize_rendering(self, screen: pygame.Surface) -> Image.Image:
        image_bytes = pygame.image.tostring(screen, RGBA_IMAGE_FORMAT)
        return Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            screen.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        return self._composition_manager.merge_in_place(surface1, surface2)

    def _render_surface_iterative(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        self._get_active_plan(renderers)
        surfaces = self._surface_collector.collect(renderers, parallel=False)
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        self._get_active_plan(renderers)
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        surfaces = self._surface_collector.collect(renderers, parallel=True)
        executor = self._get_render_executor()
        return self._composition_manager.compose_parallel(
            surfaces, executor, merge_fn=self.merge_surfaces
        )

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderMethod:
        plan = self._get_active_plan(renderers, override_renderer_variant)
        return self._resolve_render_method(plan)

    def _get_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        return self._plan_cache.get_plan(
            renderers,
            self.renderer_variant,
            override_renderer_variant,
        )

    def _get_active_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        if self._active_plan is not None:
            return self._active_plan
        return self._get_plan(renderers, override_renderer_variant)

    def _resolve_render_method(self, plan: RenderPlan) -> RenderMethod:
        return self._render_dispatch.get(
            plan.variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def render(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> pygame.Surface | None:
        return self.render_with_plan(renderers, override_renderer_variant).surface

    def render_with_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderResult:
        plan = self._get_plan(renderers, override_renderer_variant)
        render_fn = self._resolve_render_method(plan)
        self._active_plan = plan
        try:
            surface = render_fn(renderers)
        finally:
            self._active_plan = None
        return RenderResult(surface=surface, plan=plan)

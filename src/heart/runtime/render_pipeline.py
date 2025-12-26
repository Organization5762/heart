from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.render_planner import RenderPlan, RenderPlanner
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface_merge import SurfaceCompositionManager
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)


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
        self._plan_refresh_ms = Configuration.render_plan_refresh_ms()
        self._plan_cache_signature: tuple[int, ...] | None = None
        self._plan_cache_override: RendererVariant | None = None
        self._plan_cache_time = 0.0
        self._plan_cache: RenderPlan | None = None

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

    def _collect_surfaces_serial(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> list[pygame.Surface]:
        if not renderers:
            return []
        surfaces: list[pygame.Surface] = []
        for renderer in renderers:
            surface = self.process_renderer(renderer)
            if surface is not None:
                surfaces.append(surface)
        return surfaces

    def _collect_surfaces_parallel(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> list[pygame.Surface]:
        if not renderers:
            return []
        executor = self._get_render_executor()
        return [
            surface
            for surface in executor.map(self.process_renderer, renderers)
            if surface is not None
        ]

    def _render_surface_iterative(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        self._ensure_plan(renderers)
        surfaces = self._collect_surfaces_serial(renderers)
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
        self._ensure_plan(renderers)
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        surfaces = self._collect_surfaces_parallel(renderers)
        executor = self._get_render_executor()
        return self._composition_manager.compose_parallel(
            surfaces, executor, merge_fn=self.merge_surfaces
        )

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderMethod:
        plan = self._ensure_plan(renderers, override_renderer_variant)
        return self._render_dispatch.get(
            plan.variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def _ensure_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        if self._active_plan is not None:
            return self._active_plan
        self._planner.set_default_variant(self.renderer_variant)
        return self._planner.plan(renderers, override_renderer_variant)

    @staticmethod
    def _renderers_signature(
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> tuple[int, ...]:
        return tuple(id(renderer) for renderer in renderers)

    def _get_render_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        refresh_ms = self._plan_refresh_ms
        signature = self._renderers_signature(renderers)
        now = time.monotonic()
        if (
            refresh_ms > 0
            and self._plan_cache is not None
            and self._plan_cache_signature == signature
            and self._plan_cache_override == override_renderer_variant
            and ((now - self._plan_cache_time) * 1000.0) < refresh_ms
        ):
            return self._plan_cache
        self._planner.set_default_variant(self.renderer_variant)
        plan = self._planner.plan(renderers, override_renderer_variant)
        self._plan_cache_signature = signature
        self._plan_cache_override = override_renderer_variant
        self._plan_cache_time = now
        self._plan_cache = plan
        return plan

    def render(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> pygame.Surface | None:
        plan = self._get_render_plan(renderers, override_renderer_variant)
        render_fn = self._render_dispatch.get(
            plan.variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )
        self._active_plan = plan
        try:
            return render_fn(renderers)
        finally:
            self._active_plan = None

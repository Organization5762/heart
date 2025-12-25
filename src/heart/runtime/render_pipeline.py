from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface_merge import SurfaceCompositionManager
from heart.runtime.rendering.timing import RendererTimingTracker
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration
from heart.utilities.env.enums import RenderMergeStrategy
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()


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
        self._current_merge_strategy = Configuration.render_merge_strategy()
        self._composition_manager = SurfaceCompositionManager(
            strategy_provider=self._get_merge_strategy
        )
        self._timing_tracker = RendererTimingTracker()
        self._renderer_processor = RendererProcessor(
            device=device,
            peripheral_manager=peripheral_manager,
            timing_tracker=self._timing_tracker,
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

        self._render_queue_depth = 0

    def set_clock(self, clock: pygame.time.Clock | None) -> None:
        self.clock = clock

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

    def _require_clock(self) -> pygame.time.Clock:
        clock = self.clock
        if clock is None:
            raise RuntimeError("GameLoop clock is not initialized")
        return clock

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        clock = self._require_clock()
        return self._renderer_processor.process_renderer(
            renderer, clock, self._render_queue_depth
        )

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

    def _get_merge_strategy(self) -> RenderMergeStrategy:
        return self._current_merge_strategy

    def _resolve_merge_strategy(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> RenderMergeStrategy:
        configured = Configuration.render_merge_strategy()
        if configured != RenderMergeStrategy.ADAPTIVE:
            return configured
        surface_threshold = Configuration.render_merge_surface_threshold()
        if len(renderers) < surface_threshold:
            return RenderMergeStrategy.IN_PLACE
        cost_threshold_ms = Configuration.render_merge_cost_threshold_ms()
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        if cost_threshold_ms == 0:
            return RenderMergeStrategy.BATCHED
        if has_samples and estimated_cost_ms >= cost_threshold_ms:
            return RenderMergeStrategy.BATCHED
        return RenderMergeStrategy.IN_PLACE

    def _update_merge_strategy(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> None:
        self._current_merge_strategy = self._resolve_merge_strategy(renderers)

    def _log_render_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        variant: RendererVariant,
    ) -> None:
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        snapshots, missing = self._timing_tracker.snapshot(renderers)
        snapshot_payload = [
            {
                "renderer": snapshot.name,
                "average_ms": snapshot.average_ms,
                "last_ms": snapshot.last_ms,
                "samples": snapshot.sample_count,
            }
            for snapshot in snapshots
        ]
        log_message = (
            "render.plan variant=%s merge_strategy=%s renderer_count=%s "
            "estimated_cost_ms=%.2f has_samples=%s"
        )
        log_args = (
            variant.name,
            self._current_merge_strategy.value,
            len(renderers),
            estimated_cost_ms,
            has_samples,
        )
        log_extra = {
            "variant": variant.name,
            "merge_strategy": self._current_merge_strategy.value,
            "renderer_count": len(renderers),
            "estimated_cost_ms": estimated_cost_ms,
            "has_samples": has_samples,
            "renderer_timings": snapshot_payload,
            "renderer_timings_missing": missing,
        }

        log_controller.log(
            key="render.plan",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args,
            extra=log_extra,
            fallback_level=logging.DEBUG,
        )

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
        self._render_queue_depth = len(renderers)
        self._update_merge_strategy(renderers)
        surfaces = self._collect_surfaces_serial(renderers)
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        self._update_merge_strategy(renderers)
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        surfaces = self._collect_surfaces_parallel(renderers)
        executor = self._get_render_executor()
        return self._composition_manager.compose_parallel(
            surfaces, executor, merge_fn=self.merge_surfaces
        )

    def _resolve_render_variant(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RendererVariant:
        variant = override_renderer_variant or self.renderer_variant
        if variant == RendererVariant.AUTO:
            threshold = Configuration.render_parallel_threshold()
            if len(renderers) < threshold:
                return RendererVariant.ITERATIVE
            cost_threshold_ms = Configuration.render_parallel_cost_threshold_ms()
            estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
                renderers
            )
            if cost_threshold_ms == 0:
                return RendererVariant.BINARY
            if has_samples and estimated_cost_ms >= cost_threshold_ms:
                return RendererVariant.BINARY
            return RendererVariant.ITERATIVE
        return variant

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderMethod:
        variant = self._resolve_render_variant(renderers, override_renderer_variant)
        return self._render_dispatch.get(
            variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def render(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> pygame.Surface | None:
        variant = self._resolve_render_variant(renderers, override_renderer_variant)
        self._update_merge_strategy(renderers)
        self._log_render_plan(renderers, variant)
        render_fn = self._render_dispatch.get(
            variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )
        return render_fn(renderers)

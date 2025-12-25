from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.display import DisplayModeManager
from heart.runtime.rendering.surface_cache import RendererSurfaceCache
from heart.runtime.rendering.surface_merger import SurfaceMerger
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer

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
        self._display_manager = DisplayModeManager(device)
        self._surface_cache = RendererSurfaceCache(device)
        self._surface_merger = SurfaceMerger(
            lambda surface1, surface2: self.merge_surfaces(surface1, surface2)
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

    def _get_renderer_surface(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        return self._surface_cache.get_surface(renderer)

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

    def _prepare_renderer_surface(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        self._display_manager.ensure_mode(renderer.device_display_mode)
        return self._get_renderer_surface(renderer)

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        try:
            start_ns = time.perf_counter_ns()
            screen = self._render_renderer_frame(renderer)
            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
            self._log_renderer_metrics(renderer, duration_ms)
            return screen
        except Exception:
            logger.exception("Error processing renderer")
            return None

    def _render_renderer_frame(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        clock = self._require_clock()
        screen = self._prepare_renderer_surface(renderer)
        if not renderer.initialized:
            renderer.initialize(
                window=screen,
                clock=clock,
                peripheral_manager=self.peripheral_manager,
                orientation=self.device.orientation,
            )
        renderer._internal_process(
            window=screen,
            clock=clock,
            peripheral_manager=self.peripheral_manager,
            orientation=self.device.orientation,
        )
        return screen

    def _log_renderer_metrics(
        self, renderer: "StatefulBaseRenderer[Any]", duration_ms: float
    ) -> None:
        log_message = (
            "render.loop renderer=%s duration_ms=%.2f queue_depth=%s "
            "display_mode=%s uses_opengl=%s initialized=%s"
        )
        log_args = (
            renderer.name,
            duration_ms,
            self._render_queue_depth,
            renderer.device_display_mode.name,
            renderer.device_display_mode == DeviceDisplayMode.OPENGL,
            renderer.is_initialized(),
        )
        log_extra = {
            "renderer": renderer.name,
            "duration_ms": duration_ms,
            "queue_depth": self._render_queue_depth,
            "display_mode": renderer.device_display_mode.name,
            "uses_opengl": renderer.device_display_mode == DeviceDisplayMode.OPENGL,
            "initialized": renderer.is_initialized(),
        }

        log_controller.log(
            key="render.loop",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args,
            extra=log_extra,
            fallback_level=logging.DEBUG,
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

    def _merge_surfaces_in_place(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        # Ensure both surfaces are the same size
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def merge_surfaces(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        return self._merge_surfaces_in_place(surface1, surface2)

    def _compose_surfaces(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface | None:
        return self._surface_merger.merge_surfaces_serial(surfaces)

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
        surfaces = self._collect_surfaces_serial(renderers)
        return self._compose_surfaces(surfaces)

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        surfaces = self._collect_surfaces_parallel(renderers)
        if not surfaces:
            return None
        executor = self._get_render_executor()
        return self._surface_merger.merge_surfaces_parallel(surfaces, executor)

    def _resolve_render_variant(
        self,
        renderer_count: int,
        override_renderer_variant: RendererVariant | None,
    ) -> RendererVariant:
        variant = override_renderer_variant or self.renderer_variant
        if variant == RendererVariant.AUTO:
            threshold = Configuration.render_parallel_threshold()
            if threshold > 1 and renderer_count >= threshold:
                return RendererVariant.BINARY
            return RendererVariant.ITERATIVE
        return variant

    def _render_fn(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderMethod:
        variant = self._resolve_render_variant(len(renderers), override_renderer_variant)
        return self._render_dispatch.get(
            variant, self._render_dispatch[RendererVariant.ITERATIVE]
        )

    def render(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None = None,
    ) -> pygame.Surface | None:
        render_fn = self._render_fn(renderers, override_renderer_variant)
        return render_fn(renderers)

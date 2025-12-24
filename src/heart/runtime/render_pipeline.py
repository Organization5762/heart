from __future__ import annotations

import enum
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Callable, Literal, cast

import pygame
from PIL import Image

from heart import DeviceDisplayMode
from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.internal import FrameAccumulator
from heart.utilities.env import Configuration, RenderMergeStrategy
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import BaseRenderer, StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()

RGBA_IMAGE_FORMAT: Literal["RGBA"] = "RGBA"

RenderMethod = Callable[[list["StatefulBaseRenderer[Any]"]], pygame.Surface | None]


class RendererVariant(enum.StrEnum):
    BINARY = "BINARY"
    ITERATIVE = "ITERATIVE"
    AUTO = "AUTO"
    # TODO: Add more

    @classmethod
    def parse(cls, value: str) -> "RendererVariant":
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("HEART_RENDER_VARIANT must not be empty")
        try:
            return cls[normalized]
        except KeyError as exc:
            options = ", ".join(variant.name.lower() for variant in cls)
            raise ValueError(
                f"Unknown render variant '{value}'. Expected one of: {options}"
            ) from exc


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
        self._renderer_surface_cache: dict[
            tuple[int, DeviceDisplayMode, tuple[int, int]], pygame.Surface
        ] = {}
        self._composite_surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._composite_accumulator: FrameAccumulator | None = None

        self._last_render_mode = pygame.SHOWN

    def set_clock(self, clock: pygame.time.Clock | None) -> None:
        self.clock = clock

    def shutdown(self) -> None:
        if self._render_executor is not None:
            self._render_executor.shutdown(wait=True)
            self._render_executor = None

    def _get_renderer_surface(
        self, renderer: "BaseRenderer | StatefulBaseRenderer[Any]"
    ) -> pygame.Surface:
        size = self.device.full_display_size()
        if not Configuration.render_screen_cache_enabled():
            return pygame.Surface(size, pygame.SRCALPHA)

        cache_key = (id(renderer), renderer.device_display_mode, size)
        cached = self._renderer_surface_cache.get(cache_key)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._renderer_surface_cache[cache_key] = cached
        else:
            cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_surface(self, size: tuple[int, int]) -> pygame.Surface:
        if not Configuration.render_screen_cache_enabled():
            surface = pygame.Surface(size, pygame.SRCALPHA)
            surface.fill((0, 0, 0, 0))
            return surface

        cached = self._composite_surface_cache.get(size)
        if cached is None:
            cached = pygame.Surface(size, pygame.SRCALPHA)
            self._composite_surface_cache[size] = cached
        cached.fill((0, 0, 0, 0))
        return cached

    def _get_composite_accumulator(
        self, surface: pygame.Surface
    ) -> FrameAccumulator:
        if (
            self._composite_accumulator is None
            or self._composite_accumulator.surface is not surface
        ):
            self._composite_accumulator = FrameAccumulator(surface)
        else:
            self._composite_accumulator.reset()
        return self._composite_accumulator

    def _get_render_executor(self) -> ThreadPoolExecutor:
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(
                max_workers=Configuration.render_executor_max_workers()
            )
        return self._render_executor

    def process_renderer(
        self, renderer: "StatefulBaseRenderer[Any]"
    ) -> pygame.Surface | None:
        clock = self.clock
        if clock is None:
            raise RuntimeError("GameLoop clock is not initialized")

        try:
            start_ns = time.perf_counter_ns()
            if self.clock is None:
                raise RuntimeError("GameLoop clock is not initialized")
            clock = self.clock
            if renderer.device_display_mode == DeviceDisplayMode.OPENGL:
                if self._last_render_mode != pygame.OPENGL | pygame.DOUBLEBUF:
                    logger.info("Switching to OPENGL mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.OPENGL | pygame.DOUBLEBUF,
                    )
                self._last_render_mode = pygame.OPENGL | pygame.DOUBLEBUF
                screen = self._get_renderer_surface(renderer)
            else:
                if self._last_render_mode != pygame.SHOWN:
                    logger.info("Switching to SHOWN mode")
                    pygame.display.set_mode(
                        (
                            self.device.full_display_size()[0]
                            * self.device.scale_factor,
                            self.device.full_display_size()[1]
                            * self.device.scale_factor,
                        ),
                        pygame.SHOWN,
                    )
                self._last_render_mode = pygame.SHOWN
                screen = self._get_renderer_surface(renderer)

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

            duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
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
                "uses_opengl": renderer.device_display_mode
                == DeviceDisplayMode.OPENGL,
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

            return screen
        except Exception as e:
            logger.error(f"Error processing renderer: {e}", exc_info=True)
            return None

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

    def _compose_surfaces_batched(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface:
        size = surfaces[0].get_size()
        composite = self._get_composite_surface(size)
        accumulator = self._get_composite_accumulator(composite)
        for surface in surfaces:
            accumulator.queue_blit(surface)
        return accumulator.flush(clear=False)

    def _compose_surfaces(
        self, surfaces: list[pygame.Surface]
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = surfaces[0]
            for surface in surfaces[1:]:
                base = self.merge_surfaces(base, surface)
            return base
        return self._compose_surfaces_batched(surfaces)

    def _render_surface_iterative(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        if Configuration.render_merge_strategy() == RenderMergeStrategy.IN_PLACE:
            base = None
            for renderer in renderers:
                surface = self.process_renderer(renderer)
                if base is None:
                    base = surface
                elif surface is None:
                    continue
                else:
                    base = self.merge_surfaces(base, surface)
            return base

        surfaces: list[pygame.Surface] = []
        for renderer in renderers:
            surface = self.process_renderer(renderer)
            if surface is not None:
                surfaces.append(surface)
        return self._compose_surfaces_batched(surfaces) if surfaces else None

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        if not renderers:
            return None
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        self._render_queue_depth = len(renderers)
        executor = self._get_render_executor()
        surfaces: list[pygame.Surface] = [
            surface
            for surface in executor.map(self.process_renderer, renderers)
            if surface is not None
        ]

        if not surfaces:
            return None
        if Configuration.render_merge_strategy() == RenderMergeStrategy.BATCHED:
            return self._compose_surfaces_batched(surfaces)

        # Iteratively merge surfaces until only one remains
        while len(surfaces) > 1:
            pairs = list(zip(surfaces[0::2], surfaces[1::2]))

            # Merge pairs in parallel
            merged_surfaces = list(
                executor.map(lambda p: self.merge_surfaces(*p), pairs)
            )

            # If there's an odd surface out, append it to the merged list
            if len(surfaces) % 2 == 1:
                merged_surfaces.append(surfaces[-1])

            # Update the surfaces list for the next iteration
            surfaces = merged_surfaces

        return surfaces[0]

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

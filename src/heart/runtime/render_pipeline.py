from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface_merge import SurfaceCompositionManager
from heart.runtime.rendering.surface_provider import RendererSurfaceProvider
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


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
        self._surface_provider = RendererSurfaceProvider(device)
        self._composition_manager = SurfaceCompositionManager()
        self._renderer_processor = RendererProcessor(
            device=device,
            peripheral_manager=peripheral_manager,
            surface_provider=self._surface_provider,
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
            renderer=renderer,
            clock=clock,
            queue_depth=self._render_queue_depth,
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
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._render_queue_depth = len(renderers)
        if len(renderers) == 1:
            return self.process_renderer(renderers[0])
        surfaces = self._collect_surfaces_parallel(renderers)
        executor = self._get_render_executor()
        return self._composition_manager.compose_parallel(
            surfaces, executor, merge_fn=self.merge_surfaces
        )

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

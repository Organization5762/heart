from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, cast

import pygame
from PIL import Image

from heart.device import Device
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.runtime.rendering.planner import RenderPlanner
from heart.runtime.rendering.renderer_processor import RendererFrameProcessor
from heart.runtime.rendering.surface_merge import SurfaceCompositionManager
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration
from heart.utilities.env.enums import RenderMergeStrategy

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
        self._current_merge_strategy = Configuration.render_merge_strategy()
        self._composition_manager = SurfaceCompositionManager(
            strategy_provider=self._get_merge_strategy
        )
        self._renderer_processor = RendererFrameProcessor(device, peripheral_manager)
        self._timing_tracker = self._renderer_processor.timing_tracker
        self._planner = RenderPlanner(self._timing_tracker)

        binary_method = cast(RenderMethod, self._render_surfaces_binary)
        iterative_method = cast(RenderMethod, self._render_surface_iterative)
        object.__setattr__(self, "_render_surfaces_binary", binary_method)
        object.__setattr__(self, "_render_surface_iterative", iterative_method)
        self._render_dispatch: dict[RendererVariant, RenderMethod] = {
            RendererVariant.BINARY: binary_method,
            RendererVariant.ITERATIVE: iterative_method,
        }
        self._render_executor: ThreadPoolExecutor | None = None

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

    def _get_merge_strategy(self) -> RenderMergeStrategy:
        return self._current_merge_strategy

    def _resolve_merge_strategy(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> RenderMergeStrategy:
        return self._planner.resolve_merge_strategy(renderers)

    def _update_merge_strategy(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> None:
        self._current_merge_strategy = self._resolve_merge_strategy(renderers)

    def _log_render_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        variant: RendererVariant,
    ) -> None:
        self._planner.log_plan(renderers, variant, self._current_merge_strategy)

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
        self._update_merge_strategy(renderers)
        surfaces = self._collect_surfaces_serial(renderers)
        return self._composition_manager.compose_serial(
            surfaces, merge_fn=self.merge_surfaces
        )

    def _render_surfaces_binary(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> pygame.Surface | None:
        self._renderer_processor.set_queue_depth(len(renderers))
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
        return self._planner.resolve_variant(
            renderers, override_renderer_variant, self.renderer_variant
        )

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

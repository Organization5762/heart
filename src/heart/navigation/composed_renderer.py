from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)

logger = get_logger(__name__)


@dataclass
class ComposedRendererState:
    peripheral_manager: PeripheralManager
    window: DisplayContext
    orientation: Orientation


class ComposedRenderer(StatefulBaseRenderer[ComposedRendererState]):
    def __init__(
        self,
        renderers: list[RendererSpec] | None = None,
        renderer_resolver: RendererResolver | None = None,
        surface_provider: RendererSurfaceProvider | None = None,
    ) -> None:
        super().__init__()
        self._renderer_resolver = renderer_resolver
        self.renderers = [
            resolve_renderer_spec(renderer, self._renderer_resolver)
            for renderer in (renderers or [])
        ]
        self._sync_device_display_mode()
        self.surface_provider = surface_provider or RendererSurfaceProvider()

    def _real_get_renderers(self) -> list[StatefulBaseRenderer]:
        result: list[StatefulBaseRenderer] = []
        for renderer in self.renderers:
            result.extend(renderer.get_renderers())
        return result

    @property
    def name(self) -> str:
        joined = "+".join(renderer.name for renderer in self.renderers)
        return f"ComposedRenderer:{joined}"

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ComposedRendererState:
        for renderer in self.renderers:
            renderer.initialize(window, peripheral_manager, orientation)
        return ComposedRendererState(
            peripheral_manager=peripheral_manager,
            window=window,
            orientation=orientation,
        )

    def add_renderer(self, *renderers: RendererSpec) -> None:
        resolved_renderers = [
            resolve_renderer_spec(renderer, self._renderer_resolver)
            for renderer in renderers
        ]
        self.renderers.extend(resolved_renderers)
        self._sync_device_display_mode()
        if self.is_initialized():
            for item in resolved_renderers:
                item.initialize(
                    self.state.window,
                    self.state.peripheral_manager,
                    self.state.orientation,
                )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        result = self.render_batch(
            self.renderers,
            window=window,
            peripheral_manager=self.state.peripheral_manager,
            orientation=orientation,
            surface_provider=self.surface_provider,
        )
        if result is not None and window.screen is not None:
            window.screen.blit(result, (0, 0))

    def reset(self) -> None:
        for renderer in self.renderers:
            renderer.reset()
        super().reset()

    @staticmethod
    def required_display_mode(
        renderers: Sequence[StatefulBaseRenderer],
    ) -> DeviceDisplayMode:
        if any(
            renderer.device_display_mode == DeviceDisplayMode.OPENGL
            for renderer in renderers
        ):
            return DeviceDisplayMode.OPENGL
        if any(
            renderer.device_display_mode == DeviceDisplayMode.FULL
            for renderer in renderers
        ):
            return DeviceDisplayMode.FULL
        return DeviceDisplayMode.MIRRORED

    @classmethod
    def render_batch(
        cls,
        renderers: Sequence[StatefulBaseRenderer],
        *,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        surface_provider: RendererSurfaceProvider | None = None,
    ) -> pygame.Surface | None:
        helper = surface_provider or RendererSurfaceProvider()
        surfaces: list[pygame.Surface] = []
        for renderer in renderers:
            try:
                surface = cls._render_renderer(
                    renderer,
                    window=window,
                    peripheral_manager=peripheral_manager,
                    orientation=orientation,
                    surface_provider=helper,
                )
            except Exception:
                logger.exception("Error processing renderer %s", renderer.name)
                if Configuration.render_crash_on_error():
                    raise
                continue
            surfaces.append(surface)
        return cls._merge_surfaces(surfaces)

    @staticmethod
    def _render_renderer(
        renderer: StatefulBaseRenderer,
        *,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        surface_provider: RendererSurfaceProvider,
    ) -> pygame.Surface:
        scratch_window = window.get_scratch_screen(
            orientation=orientation,
            display_mode=renderer.device_display_mode,
        )
        if not renderer.initialized:
            renderer.initialize(
                window=scratch_window,
                peripheral_manager=peripheral_manager,
                orientation=orientation,
            )
        renderer._internal_process(
            window=scratch_window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        assert scratch_window.screen is not None
        return surface_provider.postprocess_input_screen(
            screen=scratch_window.screen,
            orientation=orientation,
            display_mode=renderer.device_display_mode,
        )

    @staticmethod
    def _merge_surfaces(surfaces: Sequence[pygame.Surface]) -> pygame.Surface | None:
        if not surfaces:
            return None
        base = pygame.Surface(surfaces[0].get_size(), pygame.SRCALPHA)
        base.fill((0, 0, 0, 0))
        for surface in surfaces:
            base.blit(surface, (0, 0))
        return base

    def _sync_device_display_mode(self) -> None:
        self.device_display_mode = self.required_display_mode(self.renderers)

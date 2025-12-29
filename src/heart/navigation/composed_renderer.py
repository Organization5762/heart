from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider

from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)


@dataclass
class ComposedRendererState:
    peripheral_manager: PeripheralManager
    window: pygame.Surface
    clock: pygame.time.Clock
    orientation: Orientation


class ComposedRenderer(StatefulBaseRenderer[ComposedRendererState]):
    def __init__(
        self,
        renderers: list[RendererSpec],
        surface_provider: RendererSurfaceProvider,
        renderer_resolver: RendererResolver | None = None,
    ) -> None:
        super().__init__()
        self._renderer_resolver = renderer_resolver
        self.renderers = [
            resolve_renderer_spec(renderer, renderer_resolver, "ComposedRenderer")
            for renderer in renderers
        ]
        self.device_display_mode = DeviceDisplayMode.FULL
        self.surface_provider = surface_provider

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
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ComposedRendererState:
        for renderer in self.renderers:
            
            renderer.initialize(window, clock, peripheral_manager, orientation)
        return ComposedRendererState(
            peripheral_manager=peripheral_manager,
            window=window,
            clock=clock,
            orientation=orientation,
        )

    def add_renderer(self, *renderers: RendererSpec) -> None:
        resolved_renderers = [
            resolve_renderer_spec(renderer, self._renderer_resolver, "ComposedRenderer")
            for renderer in renderers
        ]
        self.renderers.extend(resolved_renderers)
        if self.is_initialized():
            for item in resolved_renderers:
                item.initialize(
                    self.state.window,
                    self.state.clock,
                    self.state.peripheral_manager,
                    self.state.orientation,
                )

    def resolve_renderer(
        self, resolver: RendererResolver, renderer: type[StatefulBaseRenderer]
    ) -> None:
        resolved = resolver.resolve(renderer)
        self.renderers.append(resolved)
        if self.is_initialized():
            resolved.initialize(
                self.state.window,
                self.state.clock,
                self.state.peripheral_manager,
                self.state.orientation,
            )

    def resolve_renderer_from_container(
        self, renderer: type[StatefulBaseRenderer]
    ) -> None:
        self.add_renderer(renderer)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        for renderer in self.renderers:
            surface = self.surface_provider.get_input_screen(
                window=window,
                orientation=orientation,
                display_mode=renderer.device_display_mode,
            )
            renderer._internal_process(
                window=surface,
                clock=clock,
                peripheral_manager=self.state.peripheral_manager,
                orientation=orientation,
            )
            result = self.surface_provider.postprocess_input_screen(
                screen=surface,
                orientation=orientation,
                display_mode=renderer.device_display_mode,
            )
            window.blit(result, (0, 0))

    def reset(self) -> None:
        for renderer in self.renderers:
            renderer.reset()
        super().reset()

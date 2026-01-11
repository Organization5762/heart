from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider

from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)


@dataclass
class ComposedRendererState:
    peripheral_manager: PeripheralManager
    window: DisplayContext
    orientation: Orientation


class ComposedRenderer(StatefulBaseRenderer[ComposedRendererState]):
    def __init__(
        self,
        renderers: list[RendererSpec],
        surface_provider: RendererSurfaceProvider,
    ) -> None:
        super().__init__()
        self.renderers = [
            resolve_renderer_spec(renderer)
            for renderer in renderers
        ]
        if any(renderer.device_display_mode == DeviceDisplayMode.OPENGL for renderer in self.renderers):
            self.device_display_mode = DeviceDisplayMode.OPENGL
        else:
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
            resolve_renderer_spec(renderer)
            for renderer in renderers
        ]
        self.renderers.extend(resolved_renderers)
        if self.is_initialized():
            for item in resolved_renderers:
                item.initialize(
                    self.state.window,
                    self.state.window.clock,
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
                self.state.window.clock,
                self.state.peripheral_manager,
                self.state.orientation,
            )

    def resolve_renderer_from_container(
        self, renderer: type[StatefulBaseRenderer]
    ) -> None:
        self.add_renderer(renderer)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        for renderer in self.renderers:
            scartch_window = window.get_scratch_screen(
                orientation=orientation,
                display_mode=renderer.device_display_mode,
            )
            renderer._internal_process(
                window=scartch_window,
                peripheral_manager=self.state.peripheral_manager,
                orientation=orientation,
            )
            result = self.surface_provider.postprocess_input_screen(
                screen=scartch_window.screen,
                orientation=orientation,
                display_mode=renderer.device_display_mode,
            )
            window.screen.blit(result, (0, 0))

    def reset(self) -> None:
        for renderer in self.renderers:
            renderer.reset()
        super().reset()

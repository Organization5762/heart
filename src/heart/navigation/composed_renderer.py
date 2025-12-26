from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

import pygame

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)


class RendererResolver(Protocol):
    def resolve(self, dependency: type[RendererT]) -> RendererT:
        """Resolve renderer instances from the shared container."""


@dataclass
class ComposedRendererState:
    peripheral_manager: PeripheralManager
    window: pygame.Surface
    clock: pygame.time.Clock
    orientation: Orientation


class ComposedRenderer(StatefulBaseRenderer[ComposedRendererState]):
    def __init__(
        self,
        renderers: list[StatefulBaseRenderer],
        renderer_resolver: RendererResolver | None = None,
    ) -> None:
        super().__init__()
        self.renderers: list[StatefulBaseRenderer] = renderers
        self._renderer_resolver = renderer_resolver

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

    def add_renderer(self, *renderers: StatefulBaseRenderer) -> None:
        self.renderers.extend(renderers)
        if self.is_initialized():
            for item in renderers:
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
        if self._renderer_resolver is None:
            raise ValueError("ComposedRenderer requires a renderer resolver")
        self.resolve_renderer(self._renderer_resolver, renderer)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        # TODO: This overlaps a bit with what the environment does
        for renderer in self.renderers:
            renderer._internal_process(
                window,
                clock,
                self.state.peripheral_manager,
                orientation,
            )

    def reset(self) -> None:
        for renderer in self.renderers:
            renderer.reset()
        super().reset()

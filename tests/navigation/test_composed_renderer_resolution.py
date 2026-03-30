"""Validate renderer-spec resolution for composed navigation helpers."""

from __future__ import annotations

import pygame

from heart.device import Device
from heart.navigation import ComposedRenderer
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider


class _ContainerRenderer(StatefulBaseRenderer[int]):
    """Renderer used to confirm type-based composed specs resolve into instances."""

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class _RendererResolver:
    """Simple resolver that mimics the runtime container for renderer construction."""

    def resolve(
        self,
        renderer: type[_ContainerRenderer],
    ) -> _ContainerRenderer:
        return renderer()


class _ResolverSurfaceProvider(RendererSurfaceProvider):
    """Surface provider that exposes a resolver for composed renderer tests."""

    def __init__(
        self,
        display_context: DisplayContext,
        resolver: _RendererResolver,
    ) -> None:
        super().__init__(display_context)
        self._container = resolver


def _build_display_context(device: Device) -> DisplayContext:
    screen = pygame.Surface(device.scaled_display_size(), pygame.SRCALPHA)
    return DisplayContext(
        device=device,
        screen=screen,
        clock=pygame.time.Clock(),
    )


class TestComposedRendererResolution:
    """Ensure composed renderers resolve class specs while remaining execution nodes."""

    def test_resolves_renderer_types_at_construction(self, device: Device) -> None:
        """Verify constructor class specs resolve through the bound resolver so nested graphs can stay declarative."""
        display_context = _build_display_context(device)
        resolver = _RendererResolver()
        surface_provider = _ResolverSurfaceProvider(display_context, resolver)

        composed = ComposedRenderer(
            renderers=[_ContainerRenderer],
            surface_provider=surface_provider,
        )

        assert isinstance(composed.renderers[0], _ContainerRenderer)

    def test_add_renderer_resolves_types(self, device: Device) -> None:
        """Confirm add_renderer resolves class inputs so dynamic graph edits still honor shared construction rules."""
        display_context = _build_display_context(device)
        resolver = _RendererResolver()
        surface_provider = _ResolverSurfaceProvider(display_context, resolver)
        composed = ComposedRenderer(
            renderers=[],
            surface_provider=surface_provider,
        )

        composed.add_renderer(_ContainerRenderer)

        assert isinstance(composed.renderers[0], _ContainerRenderer)

    def test_get_renderers_returns_execution_node(self, device: Device) -> None:
        """Verify get_renderers returns the composed node itself so execution mode stays attached to the meta-renderer."""
        display_context = _build_display_context(device)
        resolver = _RendererResolver()
        surface_provider = _ResolverSurfaceProvider(display_context, resolver)
        composed = ComposedRenderer(
            renderers=[_ContainerRenderer()],
            surface_provider=surface_provider,
        )

        assert composed.get_renderers() == [composed]

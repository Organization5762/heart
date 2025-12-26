"""Validate Lagom-backed renderer resolution in composed navigation helpers."""

import pytest
from lagom import Container

from heart.navigation import ComposedRenderer
from heart.renderers import StatefulBaseRenderer


class _ContainerRenderer(StatefulBaseRenderer[int]):
    """Renderer used to confirm container-backed resolution paths."""

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class TestComposedRendererResolution:
    """Ensure composed renderers can resolve classes via Lagom for consistent dependency wiring."""

    def test_resolves_renderer_types_at_construction(self) -> None:
        """Verify renderer classes resolve via Lagom on init so configuration lists stay container-aware."""
        container = Container()
        container[_ContainerRenderer] = _ContainerRenderer

        composed = ComposedRenderer([_ContainerRenderer], renderer_resolver=container)

        assert isinstance(composed.renderers[0], _ContainerRenderer)

    def test_add_renderer_resolves_types(self) -> None:
        """Confirm add_renderer resolves class inputs so dynamic additions still honor container wiring."""
        container = Container()
        container[_ContainerRenderer] = _ContainerRenderer

        composed = ComposedRenderer([], renderer_resolver=container)
        composed.add_renderer(_ContainerRenderer)

        assert isinstance(composed.renderers[0], _ContainerRenderer)

    def test_requires_resolver_for_renderer_types(self) -> None:
        """Assert renderer classes require a resolver so misconfigured compositions fail fast."""
        with pytest.raises(ValueError, match="renderer resolver"):
            ComposedRenderer([_ContainerRenderer])

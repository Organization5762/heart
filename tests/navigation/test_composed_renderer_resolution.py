"""Validate Lagom-backed renderer resolution in composed navigation helpers."""


from heart.device import Device
from heart.navigation import ComposedRenderer
from heart.renderers import StatefulBaseRenderer
from heart.runtime.container import build_runtime_container
from heart.runtime.rendering.pipeline import RendererVariant


class _ContainerRenderer(StatefulBaseRenderer[int]):
    """Renderer used to confirm container-backed resolution paths."""

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class TestComposedRendererResolution:
    """Ensure composed renderers can resolve classes via Lagom for consistent dependency wiring."""

    def test_resolves_renderer_types_at_construction(self, device: Device) -> None:
        """Verify renderer classes resolve via Lagom on init so configuration lists stay container-aware."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
        )
        container[_ContainerRenderer] = _ContainerRenderer

        composed = container.resolve(ComposedRenderer)
        composed.add_renderer(_ContainerRenderer)

        assert isinstance(composed.renderers[0], _ContainerRenderer)

    def test_add_renderer_resolves_types(self, device: Device) -> None:
        """Confirm add_renderer resolves class inputs so dynamic additions still honor container wiring."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
        )
        container[_ContainerRenderer] = _ContainerRenderer

        composed = container.resolve(ComposedRenderer)
        composed.add_renderer(_ContainerRenderer)

        assert isinstance(composed.renderers[0], _ContainerRenderer)

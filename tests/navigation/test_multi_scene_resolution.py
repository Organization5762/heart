"""Validate Lagom-backed renderer resolution in multi-scene navigation helpers."""

import pytest

from heart.device import Device
from heart.navigation import MultiScene
from heart.renderers import StatefulBaseRenderer
from heart.runtime.container import build_runtime_container
from heart.runtime.rendering.pipeline import RendererVariant


class _ContainerScene(StatefulBaseRenderer[int]):
    """Renderer used to confirm container-backed resolution paths."""

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class TestMultiSceneResolution:
    """Ensure multi-scene navigation resolves class-based scenes via Lagom for consistent wiring."""

    def test_resolves_scene_types_at_construction(self, device: Device) -> None:
        """Verify scene classes resolve via Lagom at init so multi-scene compositions stay container-aware."""
        container = build_runtime_container(
            device=device,
            render_variant=RendererVariant.ITERATIVE,
        )
        container[_ContainerScene] = _ContainerScene

        multi_scene = MultiScene([_ContainerScene], renderer_resolver=container)

        assert isinstance(multi_scene.scenes[0], _ContainerScene)

    def test_requires_resolver_for_scene_types(self) -> None:
        """Assert scene classes require a resolver so misconfigured compositions fail fast."""
        with pytest.raises(ValueError, match="renderer resolver"):
            MultiScene([_ContainerScene])

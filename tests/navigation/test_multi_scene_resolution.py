"""Validate Lagom-backed renderer resolution in multi-scene navigation helpers."""

import pytest
from lagom import Container

from heart.navigation import MultiScene
from heart.renderers import StatefulBaseRenderer


class _ContainerScene(StatefulBaseRenderer[int]):
    """Renderer used to confirm container-backed resolution paths."""

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class TestMultiSceneResolution:
    """Ensure multi-scene navigation resolves class-based scenes via Lagom for consistent wiring."""

    def test_resolves_scene_types_at_construction(self) -> None:
        """Verify scene classes resolve via Lagom at init so multi-scene compositions stay container-aware."""
        container = Container()
        container[_ContainerScene] = _ContainerScene

        multi_scene = MultiScene([_ContainerScene], renderer_resolver=container)

        assert isinstance(multi_scene.scenes[0], _ContainerScene)

    def test_requires_resolver_for_scene_types(self) -> None:
        """Assert scene classes require a resolver so misconfigured compositions fail fast."""
        with pytest.raises(ValueError, match="renderer resolver"):
            MultiScene([_ContainerScene])

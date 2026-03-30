"""Validate the optional PyO3 scene-manager bridge integration points."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from heart.navigation.native_scene_manager import (PythonSceneManagerBridge,
                                                   build_scene_manager_backend)


class TestNativeSceneManagerBridge:
    """Ensure native scene-manager hooks stay replaceable so navigation can move into Rust incrementally."""

    def test_build_scene_manager_backend_falls_back_to_python(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the builder returns the Python fallback when the extension is unavailable. This keeps scene navigation usable in environments that have not installed the native bridge yet."""

        monkeypatch.setattr(
            "heart.navigation.native_scene_manager.optional_import",
            lambda *_args, **_kwargs: None,
        )

        backend = build_scene_manager_backend(["intro", "main"])

        assert isinstance(backend, PythonSceneManagerBridge)
        backend.reset_button_offset(4)
        assert backend.active_scene_index(5) == 1

    def test_build_scene_manager_backend_prefers_native_bridge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the builder instantiates the native bridge when it is importable. This keeps the runtime ready to hand off scene state to Rust without changing Python call sites."""

        class FakeBridge:
            def __init__(self, scene_names: list[str]) -> None:
                self.scene_names = scene_names

        fake_module = SimpleNamespace(SceneManagerBridge=FakeBridge)
        monkeypatch.setattr(
            "heart.navigation.native_scene_manager.optional_import",
            lambda *_args, **_kwargs: fake_module,
        )

        backend = build_scene_manager_backend(["intro", "main"])

        assert isinstance(backend, FakeBridge)
        assert backend.scene_names == ["intro", "main"]

    def test_python_scene_manager_bridge_wraps_scene_indices(self) -> None:
        """Verify the Python fallback mirrors the intended wraparound semantics. This preserves current multi-scene behaviour while the Rust bridge is still optional."""

        backend = PythonSceneManagerBridge(["intro", "main", "outro"])

        backend.reset_button_offset(10)

        assert backend.active_scene_index(10) == 0
        assert backend.active_scene_index(11) == 1
        assert backend.active_scene_index(14) == 1

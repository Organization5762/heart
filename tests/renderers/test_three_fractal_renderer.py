"""Validate three-fractal renderer lifecycle cleanup."""

from __future__ import annotations

from unittest.mock import Mock

import pygame

from heart import DeviceDisplayMode
from heart.renderers.three_fractal.provider import FractalSceneProvider
from heart.renderers.three_fractal.renderer import FractalRuntime, FractalScene
from heart.renderers.three_fractal.state import FractalSceneState


class _StubRuntime:
    def __init__(self) -> None:
        self.reset_calls = 0
        self.initialize_calls = 0
        self._initialized = True

    def reset(self) -> None:
        self.reset_calls += 1

    def is_initialized(self) -> bool:
        return self._initialized

    def initialize(self, *args, **kwargs) -> None:
        self.initialize_calls += 1
        self._initialized = True

    def real_process(self, *args, **kwargs) -> None:
        return None


class TestFractalRuntime:
    """Ensure fractal runtime cleanup is explicit so OpenGL modes do not poison later renderer lifecycles."""

    def test_initial_state_does_not_reconfigure_display_context(
        self,
        monkeypatch,
    ) -> None:
        """Verify fractal initialization avoids mutating the provided display context so scratch-window setup cannot strand later scenes in OpenGL mode."""
        runtime = FractalRuntime()
        window = Mock()
        window.get_size.return_value = (64, 64)
        window.clock = Mock()
        orientation = Mock()
        peripheral_manager = Mock()

        monkeypatch.setattr(
            "heart.renderers.three_fractal.renderer.glGetString",
            lambda _value: b"mock",
        )
        runtime.shader = Mock()
        monkeypatch.setattr(runtime, "_render", lambda: None)
        monkeypatch.setattr(runtime, "_center_mouse", lambda: None)
        monkeypatch.setattr(pygame.mouse, "set_visible", lambda _visible: None)

        runtime._create_initial_state(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )

        window.configure_window.assert_not_called()

    def test_reset_clears_cached_window_state(
        self,
        monkeypatch,
    ) -> None:
        """Verify runtime reset restores UI state and clears cached surfaces so leaving the fractal mode does not strand the app in stale OpenGL state."""
        runtime = FractalRuntime()
        runtime.target_surface = object()
        runtime.clock = object()
        runtime.window_size = (1, 2)
        runtime.real_window_size = (3, 4)
        runtime.render_size = (5, 6)
        runtime.screen_center = (7, 8)
        runtime.prev_mouse_pos = (9, 10)
        runtime.mouse_pos = (11, 12)
        runtime.last_frame_time = 1.0
        runtime.last_update_time = 2.0
        runtime.delta_real_time = 3.0
        runtime.surface_array = object()
        runtime.time_initialized = 4.0
        runtime.initialized = True
        runtime._auto_started = True
        visibility_calls: list[bool] = []
        monkeypatch.setattr(pygame.mouse, "set_visible", visibility_calls.append)

        runtime.reset()

        assert visibility_calls == [True]
        assert runtime.initialized is False
        assert runtime._auto_started is False
        assert runtime.mode == "auto"
        assert runtime.target_surface is None
        assert runtime.clock is None
        assert runtime.window_size is None
        assert runtime.real_window_size is None
        assert runtime.render_size is None
        assert runtime.screen_center is None
        assert runtime.prev_mouse_pos is None
        assert runtime.mouse_pos is None
        assert runtime.last_frame_time is None
        assert runtime.last_update_time is None
        assert runtime.delta_real_time is None
        assert runtime.surface_array is None
        assert runtime.time_initialized is None
        assert runtime.shader is None
        assert runtime.program is None
        assert runtime.mat is None
        assert runtime.prevMat is None
        assert runtime.display_texture is None
        assert runtime.framebuffer_texture is None
        assert runtime.pixels is None

    def test_is_initialized_rejects_partial_tiled_runtime_state(self) -> None:
        """Verify tiled fractal runtimes require their render-size buffers so reset races cannot execute one more broken OpenGL frame."""
        runtime = FractalRuntime()
        runtime.initialized = True
        runtime.tiled_mode = True
        runtime.shader = Mock()
        runtime.program = 1
        runtime.clock = Mock()
        runtime.mat = Mock()
        runtime.prevMat = Mock()
        runtime.window_size = (64, 64)
        runtime.surface_array = Mock()
        runtime.render_size = None
        runtime.real_window_size = (128, 64)
        runtime.pixels = Mock()
        runtime.display_texture = 1

        assert runtime.is_initialized() is False


class TestFractalScene:
    """Ensure fractal scene reset cascades into the runtime so navigation can leave OpenGL-backed modes safely."""

    def test_provider_initial_state_defers_runtime_initialization(
        self,
        monkeypatch,
    ) -> None:
        """Verify provider startup builds the runtime without initializing OpenGL so later display-mode changes cannot invalidate shaders before first render."""

        class _ProviderRuntime:
            def __init__(self, device=None) -> None:
                self.device = device
                self.initialize_calls = 0
                self.initialized = False

            def initialize(self, *args, **kwargs) -> None:
                self.initialize_calls += 1
                self.initialized = True

        monkeypatch.setattr(
            "heart.renderers.three_fractal.renderer.FractalRuntime",
            _ProviderRuntime,
        )
        provider = FractalSceneProvider(device=Mock())

        state = provider.initial_state(
            window=Mock(),
            peripheral_manager=Mock(),
            orientation=Mock(),
        )

        assert isinstance(state.runtime, _ProviderRuntime)
        assert state.runtime.initialize_calls == 0
        assert state.runtime.initialized is False

    def test_constructor_preserves_opengl_display_mode(self) -> None:
        """Verify the scene reports OPENGL after construction so the runtime allocates the correct window type for fractal rendering."""
        scene = FractalScene(provider=Mock())

        assert scene.device_display_mode == DeviceDisplayMode.OPENGL

    def test_reset_resets_runtime_and_clears_cached_state(self) -> None:
        """Verify scene reset forwards to the embedded runtime and drops cached initialization state so re-entry gets a clean OpenGL lifecycle."""
        scene = FractalScene(provider=Mock())
        runtime = _StubRuntime()
        scene.set_state(FractalSceneState(runtime=runtime))
        scene._initial_state = FractalSceneState(runtime=runtime)
        scene._peripheral_manager = Mock()
        scene.initialized = True

        scene.reset()

        assert runtime.reset_calls == 1
        assert scene._initial_state is None
        assert scene._peripheral_manager is None
        assert scene.initialized is False

    def test_real_process_reinitializes_runtime_if_nested_runtime_was_reset(self) -> None:
        """Verify the scene heals a reset nested runtime before drawing so OpenGL exit and re-entry do not leave the wrapper pointing at cleared state."""
        scene = FractalScene(provider=Mock())
        runtime = _StubRuntime()
        runtime._initialized = False
        scene.set_state(FractalSceneState(runtime=runtime))
        scene._peripheral_manager = Mock()

        scene.real_process(window=Mock(), orientation=Mock())

        assert runtime.initialize_calls == 1

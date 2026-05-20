"""Validate three-fractal renderer lifecycle cleanup."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pygame

from heart import DeviceDisplayMode
from heart.device import Cube, Layout, Orientation, Rectangle
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot)
from heart.renderers.three_fractal.provider import FractalSceneProvider
from heart.renderers.three_fractal.renderer import (FractalRuntime,
                                                    FractalScene,
                                                    _trigger_pressure)
from heart.renderers.three_fractal.state import FractalSceneState


class _StubRuntime:
    def __init__(self, *, fail_initialize: bool = False) -> None:
        self.reset_calls = 0
        self.initialize_calls = 0
        self._initialized = True
        self.fail_initialize = fail_initialize

    def reset(self) -> None:
        self.reset_calls += 1

    def is_initialized(self) -> bool:
        return self._initialized

    def initialize(self, *args, **kwargs) -> None:
        self.initialize_calls += 1
        if self.fail_initialize:
            raise RuntimeError("OpenGL unavailable")
        self._initialized = True

    def real_process(self, *args, **kwargs) -> None:
        return None


class _Subscription:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _SnapshotStream:
    def __init__(self) -> None:
        self.subscriptions: list[_Subscription] = []

    def subscribe(self, **_kwargs) -> _Subscription:
        subscription = _Subscription()
        self.subscriptions.append(subscription)
        return subscription


class _SnapshotController:
    def __init__(self) -> None:
        self.stream = _SnapshotStream()
        self.snapshot = GamepadSnapshot(connected=False, identifier=None)

    def snapshot_stream(self) -> _SnapshotStream:
        return self.stream

    def sample(self) -> GamepadSnapshot:
        return self.snapshot


class _InputIO:
    def __init__(self) -> None:
        self.keyboard = _SnapshotController()
        self.gamepad = _SnapshotController()


class _PeripheralManager:
    def __init__(self) -> None:
        self.input_io = _InputIO()


class _SamplingGamepad:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.snapshot = snapshot

    def sample(self) -> GamepadSnapshot:
        return self.snapshot


class _SamplingInputIO:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.gamepad = _SamplingGamepad(snapshot)


class _SamplingPeripheralManager:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.input_io = _SamplingInputIO(snapshot)


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
        orientation = Rectangle.with_layout(columns=1, rows=1)
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

    def test_reset_disposes_snapshot_subscriptions(
        self,
        monkeypatch,
    ) -> None:
        """Verify repeated fractal entry and exit does not accumulate live input listeners."""
        runtime = FractalRuntime()
        window = Mock()
        window.get_size.return_value = (64, 64)
        window.clock = Mock()
        manager = _PeripheralManager()

        monkeypatch.setattr(
            "heart.renderers.three_fractal.renderer.glGetString",
            lambda _value: b"mock",
        )
        monkeypatch.setattr(runtime, "_render", lambda: None)
        monkeypatch.setattr(runtime, "_center_mouse", lambda: None)
        monkeypatch.setattr(pygame.mouse, "set_visible", lambda _visible: None)

        runtime._create_initial_state(
            window=window,
            peripheral_manager=manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        runtime.reset()

        keyboard_subscription = manager.input_io.keyboard.stream.subscriptions[0]
        assert keyboard_subscription.dispose_calls == 1
        assert runtime._input_subscriptions == []

    def test_reset_deletes_owned_tiled_gl_texture(
        self,
        monkeypatch,
    ) -> None:
        """Verify runtime reset releases textures allocated during fractal initialization."""
        runtime = FractalRuntime()
        runtime.display_texture = 11
        deleted_textures: list[int] = []
        monkeypatch.setattr(pygame.mouse, "set_visible", lambda _visible: None)
        monkeypatch.setattr(
            "heart.renderers.three_fractal.renderer.glDeleteTextures",
            lambda textures: deleted_textures.extend(textures),
        )

        runtime.reset()

        assert deleted_textures == [11]

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
        monkeypatch.setattr(
            "heart.renderers.three_fractal.renderer.glDeleteTextures",
            lambda *_args: None,
        )

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

    def test_cube_tile_render_size_uses_one_physical_panel(self) -> None:
        """Verify cube rendering samples one panel before repeating it across the OpenGL window."""
        assert FractalRuntime._tile_render_size((320, 80), Cube.sides()) == (80, 80)

    def test_tile_render_size_handles_multi_row_layouts(self) -> None:
        """Verify internal tiling is layout-based instead of hardcoded to horizontal strips."""
        orientation = Orientation(Layout(columns=2, rows=2))

        assert FractalRuntime._tile_render_size((128, 64), orientation) == (64, 32)

    def test_rectangle_multi_panel_layout_enables_tiling(self) -> None:
        """Verify local rectangle layouts with multiple panels render one repeated panel."""
        orientation = Rectangle.with_layout(columns=4, rows=1)

        assert FractalRuntime._should_tile(orientation) is True
        assert FractalRuntime._tile_render_size((320, 80), orientation) == (80, 80)

    def test_controller_input_samples_current_gamepad_for_movement(
        self,
        monkeypatch,
    ) -> None:
        """Verify free-look movement does not depend on a previously delivered stream snapshot."""
        runtime = FractalRuntime()
        runtime.mat = np.identity(4, dtype=np.float32)
        runtime.prevMat = np.copy(runtime.mat)
        runtime.vel = np.zeros((3,), dtype=np.float32)
        runtime.clock = Mock()
        runtime.clock.get_time.return_value = 16
        runtime.delta_real_time = 0.016
        monkeypatch.setattr(runtime, "_process_mouse", lambda: None)
        snapshot = GamepadSnapshot(
            connected=True,
            identifier="8BitDo Lite 2",
            axes={GamepadAxis.LEFT_X: 1.0},
        )

        runtime._process_input(_SamplingPeripheralManager(snapshot))

        assert runtime._gamepad_snapshot is snapshot
        assert runtime.vel[0] > 0.0

    def test_west_button_returns_free_look_to_auto_mode(self) -> None:
        """Verify the old imperative BUTTON_Y auto-return action still works with sampled snapshots."""
        runtime = FractalRuntime()
        runtime.mode = "free"
        runtime._auto_started = True
        runtime.max_velocity = 2.0
        runtime.mat = np.identity(4, dtype=np.float32)
        runtime.vel = np.zeros((3,), dtype=np.float32)
        runtime._gamepad_snapshot = GamepadSnapshot(
            connected=True,
            identifier="8BitDo Lite 2",
            tapped_buttons=frozenset({GamepadButton.WEST}),
        )

        runtime._check_enter_auto(Mock())

        assert runtime.mode == "auto"
        assert runtime._auto_started is False
        np.testing.assert_array_equal(
            runtime.mat[3, :3],
            np.array([0.0, 0.0, 12.0], dtype=np.float32),
        )

    def test_trigger_pressure_normalizes_signed_axes(self) -> None:
        """Verify signed trigger rest values do not look active while pressed values still work."""
        assert _trigger_pressure(-1.0) == 0.0
        assert _trigger_pressure(1.0) == 1.0


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
            orientation=Rectangle.with_layout(columns=1, rows=1),
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

    def test_real_process_reinitializes_runtime_if_nested_runtime_was_reset(
        self,
    ) -> None:
        """Verify the scene heals a reset nested runtime before drawing so OpenGL exit and re-entry do not leave the wrapper pointing at cleared state."""
        scene = FractalScene(provider=Mock())
        runtime = _StubRuntime()
        runtime._initialized = False
        scene.set_state(FractalSceneState(runtime=runtime))
        scene._peripheral_manager = Mock()

        scene.real_process(window=Mock(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert runtime.initialize_calls == 1

    def test_real_process_disables_runtime_after_initialization_failure(self) -> None:
        """Verify unsupported OpenGL contexts do not throw every frame after fractal entry fails."""
        scene = FractalScene(provider=Mock())
        runtime = _StubRuntime(fail_initialize=True)
        runtime._initialized = False
        scene.set_state(FractalSceneState(runtime=runtime))
        scene._peripheral_manager = Mock()

        scene.real_process(window=Mock(), orientation=Rectangle.with_layout(columns=1, rows=1))
        scene.real_process(window=Mock(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert runtime.initialize_calls == 1
        assert scene._runtime_failed is True

"""Validate three-fractal renderer lifecycle cleanup."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np

from heart.device import Cube, Layout, Orientation, Rectangle
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
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


class _SamplingGamepad:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.snapshot = snapshot

    def sample(self, **_kwargs) -> tuple[GamepadSnapshotEvent, ...]:
        if not self.snapshot.connected:
            return ()
        return (GamepadSnapshotEvent(joystick_id=0, snapshot=self.snapshot),)


class _SamplingInputIO:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.gamepad = _SamplingGamepad(snapshot)
        self.controls = _SamplingControls(self.gamepad)


class _SamplingControls:
    def __init__(self, gamepad: _SamplingGamepad) -> None:
        self._gamepad = gamepad

    def keyboard(self) -> KeyboardSnapshot:
        return KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)

    def gamepads(self) -> tuple[GamepadSnapshotEvent, ...]:
        return self._gamepad.sample()


class _SamplingPeripheralManager:
    def __init__(self, snapshot: GamepadSnapshot) -> None:
        self.input_io = _SamplingInputIO(snapshot)


class TestFractalRuntime:
    """Ensure fractal runtime cleanup is explicit so OpenGL modes do not poison later renderer lifecycles."""

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

        assert runtime._gamepad_snapshots[0].snapshot is snapshot
        assert runtime.vel[0] > 0.0

    def test_west_button_returns_free_look_to_auto_mode(self) -> None:
        """Verify the old imperative BUTTON_Y auto-return action still works with sampled snapshots."""
        runtime = FractalRuntime()
        runtime.mode = "free"
        runtime._auto_started = True
        runtime.max_velocity = 2.0
        runtime.mat = np.identity(4, dtype=np.float32)
        runtime.vel = np.zeros((3,), dtype=np.float32)
        snapshot = GamepadSnapshot(
            connected=True,
            identifier="8BitDo Lite 2",
            tapped_buttons=frozenset({GamepadButton.WEST}),
        )
        runtime._gamepad_snapshots = (
            GamepadSnapshotEvent(joystick_id=0, snapshot=snapshot),
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

    def test_real_process_disables_runtime_after_initialization_failure(self) -> None:
        """Verify unsupported OpenGL contexts do not throw every frame after fractal entry fails."""
        scene = FractalScene(provider=Mock())
        runtime = _StubRuntime(fail_initialize=True)
        runtime._initialized = False
        scene.set_state(FractalSceneState(runtime=runtime))
        scene._peripheral_manager = Mock()

        scene.real_process(
            window=Mock(), orientation=Rectangle.with_layout(columns=1, rows=1)
        )
        scene.real_process(
            window=Mock(), orientation=Rectangle.with_layout(columns=1, rows=1)
        )

        assert runtime.initialize_calls == 1
        assert scene._runtime_failed is True

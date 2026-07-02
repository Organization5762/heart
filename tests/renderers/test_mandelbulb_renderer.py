"""Validate mandelbulb shader scene lifecycle."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pygame

from heart.device import Rectangle
from heart.display.shaders.shader_templates.mandelbulb import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.mandelbulb.renderer import (BASE_PHASE_SPEED, BASE_POWER,
                                                 COLOR_MODE_COUNT,
                                                 DEFAULT_CAMERA_DISTANCE,
                                                 DEFAULT_COLOR_MODE, MAX_POWER,
                                                 MIN_PHASE_SPEED, MIN_POWER,
                                                 MORPH_POWER_DELTA,
                                                 POWER_UNITS_PER_SECOND,
                                                 MandelbulbScene)


class _Subscription:
    def __init__(self) -> None:
        self.dispose_calls = 0

    def dispose(self) -> None:
        self.dispose_calls += 1


class _SnapshotStream:
    def __init__(self, on_emit=None) -> None:
        self.subscriptions: list[tuple[_Subscription, object]] = []
        self._on_emit = on_emit

    def subscribe(self, *, on_next) -> _Subscription:
        subscription = _Subscription()
        self.subscriptions.append((subscription, on_next))
        return subscription

    def emit(self, value: object) -> None:
        if self._on_emit is not None:
            self._on_emit(value)
        for _, on_next in self.subscriptions:
            on_next(value)


class _SnapshotController:
    def __init__(self, snapshot: object | None = None) -> None:
        self.snapshot = snapshot or GamepadSnapshot(connected=False, identifier=None)
        self.stream = _SnapshotStream(on_emit=self._set_snapshot)

    def snapshot_stream(self) -> _SnapshotStream:
        return self.stream

    def sample(self, **_kwargs) -> object:
        if isinstance(self.snapshot, GamepadSnapshot):
            if not self.snapshot.connected:
                return ()
            return (GamepadSnapshotEvent(joystick_id=0, snapshot=self.snapshot),)
        return self.snapshot

    def _set_snapshot(self, value: object) -> None:
        if isinstance(value, GamepadSnapshot | KeyboardSnapshot):
            self.snapshot = value


class _InputIO:
    def __init__(self) -> None:
        self.keyboard = _SnapshotController(
            KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)
        )
        self.gamepad = _SnapshotController()


class _PeripheralManager:
    def __init__(self) -> None:
        self.input_io = _InputIO()


class _Clock:
    def __init__(self, elapsed_ms: int) -> None:
        self.elapsed_ms = elapsed_ms

    def get_time(self) -> int:
        return self.elapsed_ms


class _ShaderRuntime:
    def __init__(self) -> None:
        self.initialize_calls = 0
        self.reset_calls = 0
        self.render_calls: list[dict[str, object]] = []
        self.draw_calls: list[dict[str, object]] = []
        self.read_to_surface_sizes: list[tuple[int, int]] = []

    def initialize(self, **_kwargs) -> None:
        self.initialize_calls += 1

    def is_initialized(self) -> bool:
        return self.initialize_calls > self.reset_calls

    def render(self, _window, *, uniforms, viewport_size) -> None:
        self.render_calls.append(
            {
                "uniforms": uniforms,
                "viewport_size": viewport_size,
            }
        )

    def draw(
        self,
        *,
        uniforms,
        viewport_size,
        viewport_origin=(0, 0),
        clear_mask="default",
    ) -> None:
        self.draw_calls.append(
            {
                "uniforms": uniforms,
                "viewport_size": viewport_size,
                "viewport_origin": viewport_origin,
                "clear_mask": clear_mask,
            }
        )

    def read_to_surface(self, _window, *, size) -> None:
        self.read_to_surface_sizes.append(size)

    def reset(self) -> None:
        self.reset_calls += 1


def _window(width: int = 100, height: int = 80) -> Mock:
    window = Mock()
    window.get_size.return_value = (width, height)
    window.clock = _Clock(100)
    return window


class TestMandelbulbScene:
    def test_shader_object_spin_uses_pauseable_auto_yaw(self) -> None:
        shader_source = (Path(shader_template_location).parent / "frag.glsl").read_text(
            encoding="utf-8"
        )

        assert "rotateY(p, uAutoYaw" in shader_source
        assert "rotateY(p, iTime * 0.2)" not in shader_source
        assert "sin(iTime * 0.4)" not in shader_source

    def test_shader_maps_right_stick_to_quadrant_palette(self) -> None:
        shader_source = (Path(shader_template_location).parent / "frag.glsl").read_text(
            encoding="utf-8"
        )

        assert "vec3 quadrantPalette(vec2 color_vector, float orbit)" in shader_source
        assert "vec3 warm = tintedPalette" in shader_source
        assert "vec3 cyan = tintedPalette" in shader_source
        assert "vec3 violet = tintedPalette" in shader_source
        assert "vec3 acid = tintedPalette" in shader_source
        assert "vec3 angleWheelPalette(vec2 color_vector, float orbit)" in shader_source
        assert "vec3 denseBandPalette(vec2 color_vector, float orbit)" in shader_source
        assert "vec3 prismPalette(vec2 color_vector, float orbit)" in shader_source
        assert "vec3 stick_palette = stickPalette(uColorVector, orbit)" in shader_source
        assert "uColorMode < 0.5" in shader_source

    def test_normal_orientation_renders_full_window_shader(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        scene.real_process(window=window, orientation=Mock())

        assert scene.render_size == (100, 80)
        render_call = shader_runtime.render_calls[-1]
        assert render_call["viewport_size"] == (100, 80)
        assert render_call["uniforms"]["iResolution"] == (100, 80)
        assert render_call["uniforms"]["iTime"] >= 0.0
        assert render_call["uniforms"]["uCameraDistance"] == 3.0
        assert render_call["uniforms"]["uPower"] == BASE_POWER
        assert render_call["uniforms"]["uColorMode"] == float(DEFAULT_COLOR_MODE)
        np.testing.assert_array_equal(
            render_call["uniforms"]["uColorVector"],
            np.zeros((2,), dtype=np.float32),
        )
        assert render_call["uniforms"]["uPhaseTime"] > 0.0
        assert render_call["uniforms"]["uAutoYaw"] > 0.0

    def test_initializes_with_real_peripheral_manager_input_io(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()

        scene.initialize(
            window=window,
            peripheral_manager=PeripheralManager(),
            orientation=Mock(),
        )

        assert scene.is_initialized() is True

    def test_keyboard_and_gamepad_update_interactive_uniforms(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.keyboard.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset(
                    {
                        pygame.K_RIGHT,
                        pygame.K_UP,
                        pygame.K_w,
                        pygame.K_SPACE,
                        pygame.K_d,
                        pygame.K_c,
                        pygame.K_o,
                    }
                ),
                timestamp_ms=1.0,
            )
        )
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.LEFT_X: 0.5,
                    GamepadAxis.LEFT_Y: -0.25,
                    GamepadAxis.RIGHT_X: 0.5,
                    GamepadAxis.RIGHT_Y: -0.75,
                },
                buttons={GamepadButton.SOUTH: True},
            )
        )

        scene.real_process(window=window, orientation=Mock())

        uniforms = shader_runtime.render_calls[-1]["uniforms"]
        assert uniforms["uCameraYaw"] > 0.0
        assert uniforms["uCameraPitch"] > 0.0
        assert uniforms["uCameraDistance"] < 3.0
        assert scene.target_power == BASE_POWER
        assert BASE_POWER < uniforms["uPower"] < scene.morph_target_power
        assert uniforms["uColorPhase"] > 0.0
        assert uniforms["uColorVector"][0] > 0.0
        assert uniforms["uColorVector"][1] > 0.0
        assert uniforms["uColorMode"] == float(DEFAULT_COLOR_MODE)
        assert uniforms["uPhaseTime"] == 0.0
        assert uniforms["uAutoYaw"] == 0.0

    def test_phase_toggle_pauses_and_resumes_without_phase_jump(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        scene.real_process(window=window, orientation=Mock())
        moving_phase = shader_runtime.render_calls[-1]["uniforms"]["uPhaseTime"]
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                tapped_buttons=frozenset({GamepadButton.WEST}),
                timestamp_monotonic=1.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())
        paused_phase = shader_runtime.render_calls[-1]["uniforms"]["uPhaseTime"]
        scene.real_process(window=window, orientation=Mock())

        assert paused_phase == moving_phase
        assert shader_runtime.render_calls[-1]["uniforms"]["uPhaseTime"] == paused_phase

        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                tapped_buttons=frozenset({GamepadButton.WEST}),
                timestamp_monotonic=2.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert shader_runtime.render_calls[-1]["uniforms"]["uPhaseTime"] > paused_phase

    def test_left_stick_click_pauses_and_resumes_auto_orbit_without_jump(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        scene.real_process(window=window, orientation=Mock())
        moving_yaw = shader_runtime.render_calls[-1]["uniforms"]["uAutoYaw"]
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                tapped_buttons=frozenset({GamepadButton.L3}),
                timestamp_monotonic=1.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())
        paused_yaw = shader_runtime.render_calls[-1]["uniforms"]["uAutoYaw"]
        scene.real_process(window=window, orientation=Mock())

        assert paused_yaw == moving_yaw
        assert shader_runtime.render_calls[-1]["uniforms"]["uAutoYaw"] == paused_yaw

        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                tapped_buttons=frozenset({GamepadButton.L3}),
                timestamp_monotonic=2.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert shader_runtime.render_calls[-1]["uniforms"]["uAutoYaw"] > paused_yaw

    def test_right_stick_color_vector_is_sticky(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.RIGHT_X: -0.8,
                    GamepadAxis.RIGHT_Y: 0.6,
                },
            )
        )
        scene.real_process(window=window, orientation=Mock())
        selected = shader_runtime.render_calls[-1]["uniforms"]["uColorVector"].copy()

        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(connected=True, identifier="pad")
        )
        scene.real_process(window=window, orientation=Mock())

        np.testing.assert_array_equal(
            shader_runtime.render_calls[-1]["uniforms"]["uColorVector"],
            selected,
        )

    def test_right_stick_click_cycles_color_mode_once_per_tap(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                tapped_buttons=frozenset({GamepadButton.R3}),
                timestamp_monotonic=1.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.color_mode == (DEFAULT_COLOR_MODE + 1) % COLOR_MODE_COUNT
        assert shader_runtime.render_calls[-1]["uniforms"]["uColorMode"] == float(
            scene.color_mode
        )

        scene.real_process(window=window, orientation=Mock())

        assert scene.color_mode == (DEFAULT_COLOR_MODE + 1) % COLOR_MODE_COUNT

        for timestamp in range(2, COLOR_MODE_COUNT + 2):
            manager.input_io.gamepad.stream.emit(
                GamepadSnapshot(
                    connected=True,
                    identifier="pad",
                    tapped_buttons=frozenset({GamepadButton.R3}),
                    timestamp_monotonic=float(timestamp),
                )
            )
            scene.real_process(window=window, orientation=Mock())

        assert scene.color_mode == (DEFAULT_COLOR_MODE + 1) % COLOR_MODE_COUNT

    def test_morph_button_temporarily_wraps_from_current_target_power(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        scene.target_power = 10.0
        scene.power = 10.0
        manager.input_io.keyboard.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset({pygame.K_SPACE}),
                timestamp_ms=1.0,
            )
        )
        scene.real_process(window=window, orientation=Mock())

        uniforms = shader_runtime.render_calls[-1]["uniforms"]
        expected_morph_target = (
            (10.0 + MORPH_POWER_DELTA - MIN_POWER) % (MAX_POWER - MIN_POWER)
        ) + MIN_POWER
        assert scene.morph_target_power == expected_morph_target
        assert scene.target_power == 10.0
        assert expected_morph_target < uniforms["uPower"] < 10.0

        manager.input_io.keyboard.stream.emit(
            KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=2.0)
        )
        scene.real_process(window=window, orientation=Mock())

        returned_uniforms = shader_runtime.render_calls[-1]["uniforms"]
        assert returned_uniforms["uPower"] > uniforms["uPower"]
        assert scene.target_power == 10.0

    def test_triggers_lerp_power_without_zooming(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_RIGHT: 1.0},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        uniforms = shader_runtime.render_calls[-1]["uniforms"]
        assert scene.target_power > BASE_POWER
        assert BASE_POWER < uniforms["uPower"] < scene.target_power
        assert uniforms["uCameraDistance"] == 3.0

        scene.target_power = MIN_POWER + 0.05
        scene.power = MIN_POWER + 0.05
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 1.0},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.target_power == MIN_POWER

    def test_trigger_power_input_normalizes_signed_trigger_axes(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.TRIGGER_RIGHT: -1.0,
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                },
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.target_power == BASE_POWER

        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.TRIGGER_RIGHT: 1.0,
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                },
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.target_power == BASE_POWER + POWER_UNITS_PER_SECOND * 0.1

    def test_plus_minus_adjust_phase_speed_without_zooming(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.PLUS: True},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        fast_phase = shader_runtime.render_calls[-1]["uniforms"]["uPhaseTime"]
        assert scene.phase_speed > BASE_PHASE_SPEED
        assert fast_phase > 0.1
        assert shader_runtime.render_calls[-1]["uniforms"]["uCameraDistance"] == 3.0

        scene.phase_speed = MIN_PHASE_SPEED + 0.01
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.MINUS: True},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.phase_speed == MIN_PHASE_SPEED

    def test_zl_zr_zoom_without_changing_phase_speed(self) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window()
        manager = _PeripheralManager()

        scene.initialize(window=window, peripheral_manager=manager, orientation=Mock())
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.ZR: True},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.camera_distance < DEFAULT_CAMERA_DISTANCE
        assert scene.phase_speed == BASE_PHASE_SPEED

        scene.camera_distance = DEFAULT_CAMERA_DISTANCE
        manager.input_io.gamepad.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.ZL: True},
            )
        )
        scene.real_process(window=window, orientation=Mock())

        assert scene.camera_distance > DEFAULT_CAMERA_DISTANCE
        assert scene.phase_speed == BASE_PHASE_SPEED

    def test_multi_panel_rectangle_renders_mirrored_tile_across_window(
        self, monkeypatch
    ) -> None:
        scene = MandelbulbScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        window = _window(width=320, height=80)
        manager = _PeripheralManager()
        gl_begin_calls: list[int] = []
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glGenTextures",
            lambda _count: 7,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glBindTexture",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glTexParameteri",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glTexImage2D",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glReadPixels",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glTexSubImage2D",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glViewport",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glMatrixMode",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glLoadIdentity",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glOrtho",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glUseProgram",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glEnable",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glClear",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glBegin",
            lambda *args: gl_begin_calls.append(args[0]),
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glTexCoord2f",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glVertex2f",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glEnd",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.mandelbulb.renderer.glDisable",
            lambda *_args: None,
        )

        scene.initialize(
            window=window,
            peripheral_manager=manager,
            orientation=Rectangle.with_layout(columns=4, rows=1),
        )
        scene.real_process(
            window=window,
            orientation=Rectangle.with_layout(columns=4, rows=1),
        )

        assert scene.tiled_mode is True
        assert scene.render_size == (80, 80)
        assert shader_runtime.draw_calls[-1]["viewport_size"] == (80, 80)
        assert scene.display_texture == 7
        assert scene.tile_pixels is not None
        assert scene.tile_pixels.shape == (80, 80, 4)
        assert len(gl_begin_calls) == 4
        assert shader_runtime.read_to_surface_sizes == [(320, 80)]

    def test_render_size_handles_multi_row_layouts(self) -> None:
        orientation = Rectangle.with_layout(columns=2, rows=2)

        assert MandelbulbScene._render_size((128, 64), orientation) == (64, 32)
        assert MandelbulbScene._should_tile(orientation) is True

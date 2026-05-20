"""Validate controller-driven audio storm shader mode."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pygame
import pytest

from heart import DeviceDisplayMode
from heart.device import Cube, Layout, Rectangle
from heart.display.shaders.fullscreen import TextureUniform
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, KeyboardSnapshot)
from heart.renderers.audio_storm import renderer as audio_storm_module
from heart.renderers.audio_storm.renderer import (
    AUDIO_TEXTURE_HEIGHT, AUDIO_TEXTURE_WIDTH, DEFAULT_VOICE_PALETTE,
    FREE_VOICE_RANDOMIZATION_BOUNDS, ORBIT_INITIAL_PHASE, SYNTH_WRITE_X_CENTER,
    AudioStormScene)


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

    def sample(self) -> object:
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
        self.keyboard_controller = self.input_io.keyboard
        self.gamepad_controller = self.input_io.gamepad


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

    def draw(self, *, uniforms, viewport_size) -> None:
        self.draw_calls.append(
            {
                "uniforms": uniforms,
                "viewport_size": viewport_size,
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


def _calibrate_triggers(
    scene: AudioStormScene,
    manager: _PeripheralManager,
    *,
    left: float = -1.0,
    right: float = -1.0,
) -> None:
    manager.gamepad_controller.stream.emit(
        GamepadSnapshot(
            connected=True,
            identifier="pad",
            axes={
                GamepadAxis.TRIGGER_LEFT: left,
                GamepadAxis.TRIGGER_RIGHT: right,
            },
        )
    )
    scene.real_process(
        window=_window(),
        orientation=Rectangle.with_layout(columns=1, rows=1),
    )


def _stub_texture_gl(monkeypatch, *, texture_id: int = 9) -> dict[str, list[object]]:
    calls: dict[str, list[object]] = {
        "bind": [],
        "params": [],
        "image": [],
        "sub_image": [],
        "delete": [],
    }
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glGenTextures",
        lambda _count: texture_id,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glBindTexture",
        lambda *args: calls["bind"].append(args),
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glTexParameteri",
        lambda *args: calls["params"].append(args),
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glTexImage2D",
        lambda *args: calls["image"].append(args),
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glTexSubImage2D",
        lambda *args: calls["sub_image"].append(args),
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glDeleteTextures",
        lambda *args: calls["delete"].append(args),
    )
    return calls


def _stub_tile_gl(monkeypatch) -> list[int]:
    gl_begin_calls: list[int] = []
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glReadPixels",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glViewport",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glMatrixMode",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glLoadIdentity",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glOrtho",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glUseProgram",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glEnable",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glClear",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glBegin",
        lambda *args: gl_begin_calls.append(args[0]),
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glTexCoord2f",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glVertex2f",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glEnd",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        "heart.renderers.audio_storm.renderer.glDisable",
        lambda *_args: None,
    )
    return gl_begin_calls


def _energy_centroid(energy: np.ndarray) -> tuple[float, float]:
    total = float(energy.sum())
    assert total > 0.0
    y_indices, x_indices = np.indices(energy.shape, dtype=np.float32)
    return (
        float((energy * x_indices).sum() / total / energy.shape[1]),
        float((energy * y_indices).sum() / total / energy.shape[0]),
    )


class TestAudioStormScene:
    def test_constructor_uses_opengl_display_mode(self) -> None:
        scene = AudioStormScene()

        assert scene.device_display_mode == DeviceDisplayMode.OPENGL

    def test_shoulder_inputs_write_audio_texture_uniform(self, monkeypatch) -> None:
        scene = AudioStormScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        manager = _PeripheralManager()
        window = _window()
        gl_calls = _stub_texture_gl(monkeypatch, texture_id=42)

        scene.initialize(window=window, peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={
                    GamepadButton.ZL: True,
                    GamepadButton.ZR: True,
                },
                axes={
                    GamepadAxis.TRIGGER_LEFT: 0.8,
                    GamepadAxis.TRIGGER_RIGHT: 0.6,
                },
            )
        )
        scene.real_process(window=window, orientation=Rectangle.with_layout(columns=1, rows=1))

        render_call = shader_runtime.render_calls[-1]
        assert render_call["viewport_size"] == (100, 80)
        assert render_call["uniforms"]["u_resolution"] == (100, 80)
        assert render_call["uniforms"]["u_audio"] == TextureUniform(texture_id=42)
        assert render_call["uniforms"]["u_orbit_phase"] == pytest.approx(
            ORBIT_INITIAL_PHASE,
            abs=0.05,
        )
        assert scene.audio_energy.max() > 0.0
        assert scene.audio_pixels[:, :, 2].max() > 0
        centroid_x, _centroid_y = _energy_centroid(scene.audio_energy)
        assert abs(centroid_x - SYNTH_WRITE_X_CENTER) < 0.04
        assert gl_calls["image"]
        assert gl_calls["sub_image"]
        sub_image = gl_calls["sub_image"][-1]
        assert sub_image[4:6] == (AUDIO_TEXTURE_WIDTH, AUDIO_TEXTURE_HEIGHT)

    def test_keyboard_fallback_writes_energy(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.keyboard_controller.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset({pygame.K_q, pygame.K_e, pygame.K_z, pygame.K_x}),
                timestamp_ms=1.0,
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert scene.audio_energy.max() > 0.0

    def test_left_stick_aims_pulse_position_and_band(self, monkeypatch) -> None:
        baseline_scene = AudioStormScene()
        baseline_scene.shader_runtime = _ShaderRuntime()
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        baseline_manager = _PeripheralManager()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        baseline_scene.initialize(
            window=_window(),
            peripheral_manager=baseline_manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        _calibrate_triggers(baseline_scene, baseline_manager)
        _calibrate_triggers(scene, manager)
        baseline_manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 1.0},
            )
        )
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.LEFT_X: 1.0,
                    GamepadAxis.LEFT_Y: -1.0,
                    GamepadAxis.TRIGGER_LEFT: 1.0,
                },
            )
        )
        baseline_scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        baseline_x, baseline_y = _energy_centroid(baseline_scene.audio_energy)
        shifted_x, shifted_y = _energy_centroid(scene.audio_energy)
        assert shifted_x > baseline_x
        assert shifted_y > baseline_y

    def test_right_stick_and_south_button_shape_pulse(self, monkeypatch) -> None:
        base_scene = AudioStormScene()
        base_scene.shader_runtime = _ShaderRuntime()
        boosted_scene = AudioStormScene()
        boosted_scene.shader_runtime = _ShaderRuntime()
        base_manager = _PeripheralManager()
        boosted_manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        base_scene.initialize(
            window=_window(),
            peripheral_manager=base_manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        boosted_scene.initialize(
            window=_window(),
            peripheral_manager=boosted_manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        _calibrate_triggers(base_scene, base_manager, left=0.0)
        _calibrate_triggers(boosted_scene, boosted_manager, left=0.0)
        base_manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 0.1},
            )
        )
        boosted_manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.SOUTH: True},
                axes={
                    GamepadAxis.TRIGGER_LEFT: 0.1,
                    GamepadAxis.RIGHT_X: 1.0,
                    GamepadAxis.RIGHT_Y: -1.0,
                },
            )
        )

        base_scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        boosted_scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert boosted_scene.audio_energy.sum() > base_scene.audio_energy.sum()
        assert np.count_nonzero(boosted_scene.audio_energy > 0.5) > np.count_nonzero(
            base_scene.audio_energy > 0.5
        )

    def test_trigger_shoulders_are_treated_as_digital_inputs(self, monkeypatch) -> None:
        light_scene = AudioStormScene()
        light_scene.shader_runtime = _ShaderRuntime()
        full_scene = AudioStormScene()
        full_scene.shader_runtime = _ShaderRuntime()
        light_manager = _PeripheralManager()
        full_manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        light_scene.initialize(
            window=_window(),
            peripheral_manager=light_manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        full_scene.initialize(
            window=_window(),
            peripheral_manager=full_manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        light_manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 0.1},
            )
        )
        full_manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 1.0},
            )
        )

        light_scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        full_scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        np.testing.assert_array_equal(light_scene.audio_energy, full_scene.audio_energy)

    def test_held_shoulders_continue_writing_energy(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)
        monkeypatch.setattr(
            audio_storm_module,
            "AUDIO_DECAY_PER_SECOND",
            0.0,
        )

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        _calibrate_triggers(scene, manager)
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.TRIGGER_LEFT: 1.0},
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        first_frame_energy = float(scene.audio_energy.sum())
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert scene.audio_energy.sum() > first_frame_energy

    def test_scene_enters_with_default_voice_palette(self) -> None:
        scene = AudioStormScene()

        assert scene._voice_palette == DEFAULT_VOICE_PALETTE

    def test_east_button_randomizes_voice_palette_once_per_press(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.EAST: True},
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        randomized_palette = scene._voice_palette
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert randomized_palette != DEFAULT_VOICE_PALETTE
        assert scene._voice_palette == randomized_palette
        for voice in (
            randomized_palette.kick,
            randomized_palette.snare,
            randomized_palette.closed_hat,
            randomized_palette.open_hat,
        ):
            assert voice.bands
            for band in voice.bands:
                assert FREE_VOICE_RANDOMIZATION_BOUNDS.center_y.low <= band.center_y
                assert band.center_y <= FREE_VOICE_RANDOMIZATION_BOUNDS.center_y.high

    def test_randomized_palette_uses_same_bounds_for_all_trigger_slots(
        self,
        monkeypatch,
    ) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.EAST: True},
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        for voice in (
            scene._voice_palette.kick,
            scene._voice_palette.snare,
            scene._voice_palette.closed_hat,
            scene._voice_palette.open_hat,
        ):
            assert len(voice.bands) <= FREE_VOICE_RANDOMIZATION_BOUNDS.band_count[1]
            assert voice.gain >= FREE_VOICE_RANDOMIZATION_BOUNDS.voice_gain.low
            assert voice.gain <= FREE_VOICE_RANDOMIZATION_BOUNDS.voice_gain.high

    def test_period_key_logs_current_voice_palette_once_per_press(
        self,
        monkeypatch,
    ) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        logger_info = Mock()
        _stub_texture_gl(monkeypatch)
        monkeypatch.setattr(audio_storm_module.logger, "info", logger_info)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.keyboard_controller.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset({pygame.K_PERIOD}),
                timestamp_ms=1.0,
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        logger_info.assert_called_once()
        assert logger_info.call_args.args[0] == "Current Audio Storm SynthPalette:\n%s"
        assert "SynthPalette(" in logger_info.call_args.args[1]
        assert "SynthVoice(" in logger_info.call_args.args[1]

    def test_palette_reset_restores_default_voices_after_randomize(
        self,
        monkeypatch,
    ) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.keyboard_controller.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset({pygame.K_c}),
                timestamp_ms=1.0,
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        assert scene._voice_palette != DEFAULT_VOICE_PALETTE

        scene.reset()

        assert scene._voice_palette == DEFAULT_VOICE_PALETTE

    def test_zl_writes_visible_closed_hat_bands(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.ZL: True},
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        _centroid_x, centroid_y = _energy_centroid(scene.audio_energy)
        assert 0.35 < centroid_y < 0.7

    def test_west_button_freezes_decay_and_scroll(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        scene.audio_energy[20, 30] = 0.8
        original_energy = scene.audio_energy.copy()
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.WEST: True},
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        np.testing.assert_array_equal(scene.audio_energy, original_energy)

    def test_keyboard_reverses_scroll_direction(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)
        monkeypatch.setattr(
            audio_storm_module,
            "AUDIO_DECAY_PER_SECOND",
            0.0,
        )
        monkeypatch.setattr(
            audio_storm_module,
            "AUDIO_SCROLL_PIXELS_PER_SECOND",
            10.0,
        )

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        scene.audio_energy[20, 30] = 0.8
        manager.keyboard_controller.stream.emit(
            KeyboardSnapshot(
                pressed_keys=frozenset({pygame.K_d}),
                timestamp_ms=1.0,
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert scene.audio_energy[20, 31] == 0.8
        assert scene.audio_energy[20, 30] == 0.0

    def test_signed_trigger_axes_are_normalized(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                    GamepadAxis.TRIGGER_RIGHT: -1.0,
                },
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))
        resting_energy = float(scene.audio_energy.max())
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.TRIGGER_LEFT: 1.0,
                    GamepadAxis.TRIGGER_RIGHT: -1.0,
                },
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert resting_energy == 0.0
        assert scene.audio_energy.max() > 0.0

    def test_reversed_signed_trigger_axes_are_normalized(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        _stub_texture_gl(monkeypatch)

        scene.initialize(window=_window(), peripheral_manager=manager, orientation=Rectangle.with_layout(columns=1, rows=1))
        _calibrate_triggers(scene, manager, left=1.0, right=1.0)
        resting_energy = float(scene.audio_energy.max())
        manager.gamepad_controller.stream.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                    GamepadAxis.TRIGGER_RIGHT: 1.0,
                },
            )
        )
        scene.real_process(window=_window(), orientation=Rectangle.with_layout(columns=1, rows=1))

        assert resting_energy == 0.0
        assert scene.audio_energy.max() > 0.0

    def test_cube_orientation_renders_square_tile_across_window(self, monkeypatch) -> None:
        scene = AudioStormScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        manager = _PeripheralManager()
        window = _window(width=320, height=80)
        _stub_texture_gl(monkeypatch)
        gl_begin_calls = _stub_tile_gl(monkeypatch)

        scene.initialize(
            window=window,
            peripheral_manager=manager,
            orientation=Cube.sides(),
        )
        scene.real_process(window=window, orientation=Cube.sides())

        assert scene.tiled_mode is True
        assert scene.render_size == (80, 80)
        assert [call["viewport_size"] for call in shader_runtime.draw_calls] == [(80, 80)]
        assert len(gl_begin_calls) == 4
        assert shader_runtime.read_to_surface_sizes == [(320, 80)]

    def test_cube_render_size_uses_layout_panel_dimensions(self) -> None:
        orientation = Cube(Layout(columns=2, rows=2))

        assert AudioStormScene._render_size((128, 64), orientation) == (64, 32)

    def test_rectangle_multi_panel_render_size_uses_layout_panel_dimensions(self) -> None:
        orientation = Rectangle.with_layout(columns=4, rows=1)

        assert AudioStormScene._render_size((320, 80), orientation) == (80, 80)
        assert AudioStormScene._should_tile(orientation) is True

    def test_reset_clears_input_snapshots_and_resources(self, monkeypatch) -> None:
        scene = AudioStormScene()
        scene.shader_runtime = _ShaderRuntime()
        manager = _PeripheralManager()
        gl_calls = _stub_texture_gl(monkeypatch)

        scene.initialize(
            window=_window(),
            peripheral_manager=manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        scene._ensure_audio_texture()
        scene.display_texture = 11
        scene.reset()

        assert manager.keyboard_controller.stream.subscriptions == []
        assert gl_calls["delete"] == [([11],), ([9],)]
        assert scene.window_size is None
        assert scene.render_size is None
        assert scene.tiled_mode is False
        assert np.count_nonzero(scene.audio_energy) == 0

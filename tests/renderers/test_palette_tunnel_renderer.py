"""Validate palette tunnel shader mode lifecycle and controls."""

from __future__ import annotations

from unittest.mock import Mock

import numpy as np
import pygame

from heart.device import Cube, Layout, Rectangle
from heart.peripheral.core.input import (GamepadAxis, GamepadDpadValue,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.renderers.palette_tunnel.renderer import (MOUSE_SCALE,
                                                     PaletteTunnelScene)


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
        self.stream = _SnapshotStream(on_emit=self._set_snapshot)
        self.snapshot = snapshot or GamepadSnapshot(connected=False, identifier=None)

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
    def __init__(self, gamepad_snapshot: GamepadSnapshot | None = None) -> None:
        self.keyboard = _SnapshotController(
            KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)
        )
        self.gamepad = _SnapshotController(gamepad_snapshot)
        self.controls = _ControlSurface(self)


class _ControlSurface:
    def __init__(self, input_io: _InputIO) -> None:
        self._input_io = input_io

    def keyboard(self) -> KeyboardSnapshot:
        return self._input_io.keyboard.snapshot  # type: ignore[return-value]

    def gamepads(self) -> tuple[GamepadSnapshotEvent, ...]:
        return self._input_io.gamepad.sample()  # type: ignore[return-value]


class _PeripheralManager:
    def __init__(self, gamepad_snapshot: GamepadSnapshot | None = None) -> None:
        self.input_io = _InputIO(gamepad_snapshot)


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
        self.read_surface_sizes: list[tuple[int, int]] = []
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

    def read_surface(self, *, size) -> pygame.Surface:
        self.read_surface_sizes.append(size)
        return pygame.Surface(size)

    def read_to_surface(self, _window, *, size) -> None:
        self.read_to_surface_sizes.append(size)

    def reset(self) -> None:
        self.reset_calls += 1


def _window(width: int = 100, height: int = 80) -> Mock:
    window = Mock()
    window.get_size.return_value = (width, height)
    window.clock = _Clock(100)
    return window


class TestPaletteTunnelScene:
    def test_gamepad_and_keyboard_move_virtual_cursor(self) -> None:
        scene = PaletteTunnelScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        gamepad_snapshot = GamepadSnapshot(
            connected=True,
            identifier="pad",
            axes={
                GamepadAxis.LEFT_X: 0.5,
                GamepadAxis.LEFT_Y: -0.25,
            },
            dpad=GamepadDpadValue(x=0, y=1),
        )
        manager = _PeripheralManager(gamepad_snapshot)
        window = _window()

        scene.initialize(
            window=window,
            peripheral_manager=manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        initial_cursor = scene.cursor.copy()
        manager.input_io.keyboard.stream.emit(
            KeyboardSnapshot(pressed_keys=frozenset({pygame.K_d}), timestamp_ms=1.0)
        )
        manager.input_io.gamepad.stream.emit(gamepad_snapshot)

        scene.real_process(
            window=window,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )

        assert scene.cursor[0] > initial_cursor[0]
        assert scene.cursor[1] > initial_cursor[1]
        render_call = shader_runtime.render_calls[-1]
        assert render_call["viewport_size"] == (100, 80)
        np.testing.assert_array_equal(render_call["uniforms"]["iMouse"], scene.cursor)
        np.testing.assert_array_equal(
            render_call["uniforms"]["iMouseScale"],
            MOUSE_SCALE,
        )
        assert render_call["uniforms"]["iViewportOrigin"] == (0, 0)

    def test_gamepad_stick_sample_moves_virtual_cursor_without_stream_emit(
        self,
    ) -> None:
        scene = PaletteTunnelScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        manager = _PeripheralManager(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                axes={GamepadAxis.LEFT_X: 1.0},
            )
        )
        window = _window()

        scene.initialize(
            window=window,
            peripheral_manager=manager,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )
        initial_cursor = scene.cursor.copy()
        scene.real_process(
            window=window,
            orientation=Rectangle.with_layout(columns=1, rows=1),
        )

        assert scene.cursor[0] > initial_cursor[0]
        assert scene.cursor[1] == initial_cursor[1]

    def test_cube_orientation_renders_square_tile_across_window(
        self, monkeypatch
    ) -> None:
        scene = PaletteTunnelScene()
        shader_runtime = _ShaderRuntime()
        scene.shader_runtime = shader_runtime
        manager = _PeripheralManager()
        window = _window(width=320, height=80)
        gl_begin_calls: list[int] = []
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glGenTextures",
            lambda _count: 7,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glBindTexture",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glTexParameteri",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glTexImage2D",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glReadPixels",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glTexSubImage2D",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glViewport",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glMatrixMode",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glLoadIdentity",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glOrtho",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glUseProgram",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glEnable",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glClear",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glBegin",
            lambda *args: gl_begin_calls.append(args[0]),
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glTexCoord2f",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glVertex2f",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glEnd",
            lambda *_args: None,
        )
        monkeypatch.setattr(
            "heart.renderers.palette_tunnel.renderer.glDisable",
            lambda *_args: None,
        )

        scene.initialize(
            window=window,
            peripheral_manager=manager,
            orientation=Cube.sides(),
        )
        scene.real_process(window=window, orientation=Cube.sides())

        assert scene.tiled_mode is True
        assert scene.render_size == (80, 80)
        assert [call["viewport_size"] for call in shader_runtime.draw_calls] == [
            (80, 80)
        ]
        assert shader_runtime.draw_calls[0]["viewport_origin"] == (0, 0)
        assert shader_runtime.draw_calls[0]["uniforms"]["iViewportOrigin"] == (0, 0)
        assert scene.display_texture == 7
        assert scene.tile_pixels is not None
        assert scene.tile_pixels.shape == (80, 80, 4)
        assert len(gl_begin_calls) == 4
        assert shader_runtime.read_to_surface_sizes == [(320, 80)]

    def test_cube_render_size_uses_layout_panel_dimensions(self) -> None:
        orientation = Cube(Layout(columns=2, rows=2))

        assert PaletteTunnelScene._render_size((128, 64), orientation) == (64, 32)

    def test_rectangle_multi_panel_render_size_uses_layout_panel_dimensions(
        self,
    ) -> None:
        orientation = Rectangle.with_layout(columns=4, rows=1)

        assert PaletteTunnelScene._render_size((320, 80), orientation) == (80, 80)
        assert PaletteTunnelScene._should_tile(orientation) is True

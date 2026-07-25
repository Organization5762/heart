from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame
from OpenGL.error import GLError
from OpenGL.GL import (GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_MODELVIEW,
                       GL_NEAREST, GL_PROJECTION, GL_QUADS, GL_RGBA,
                       GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER,
                       GL_TEXTURE_MIN_FILTER, GL_UNSIGNED_BYTE, glBegin,
                       glBindTexture, glClear, glDeleteTextures, glDisable,
                       glEnable, glEnd, glGenTextures, glLoadIdentity,
                       glMatrixMode, glOrtho, glReadPixels, glTexCoord2f,
                       glTexImage2D, glTexParameteri, glTexSubImage2D,
                       glUseProgram, glVertex2f, glViewport)

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.shaders.fullscreen import (FullscreenShaderRuntime,
                                              UniformValue)
from heart.display.shaders.shader_templates.palette_tunnel import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

CURSOR_SPEED_PX_PER_SECOND = 220.0
MOUSE_SCALE = np.array((2.0, 1.5), dtype=np.float32)
GAMEPAD_DEAD_ZONE = 0.12
KEYBOARD_FAST_MULTIPLIER = 2.0


@dataclass
class PaletteTunnelState:
    peripheral_manager: PeripheralManager
    start_time: float


class PaletteTunnelScene(StatefulBaseRenderer[PaletteTunnelState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.shader_runtime = FullscreenShaderRuntime()
        self.window_size: tuple[int, int] | None = None
        self.render_size: tuple[int, int] | None = None
        self.tiled_mode = False
        self.display_texture: int | None = None
        self.tile_pixels: np.ndarray | None = None
        self.cursor = np.zeros((2,), dtype=np.float32)
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots: tuple[GamepadSnapshotEvent, ...] = ()

    def is_initialized(self) -> bool:
        return (
            super().is_initialized()
            and self.shader_runtime.is_initialized()
            and self.window_size is not None
            and self.render_size is not None
        )

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> PaletteTunnelState:
        self.window_size = window.get_size()
        self.render_size = self._render_size(self.window_size, orientation)
        self.tiled_mode = self._should_tile(orientation)
        self.cursor = self._initial_cursor(self.render_size)
        self._initialize_shader()
        return PaletteTunnelState(
            peripheral_manager=peripheral_manager,
            start_time=time.monotonic(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        self._refresh_keyboard_snapshot()
        self._refresh_gamepad_snapshot()
        render_size = self._render_size(window.get_size(), orientation)
        if self.window_size != window.get_size() or self.render_size != render_size:
            self.window_size = window.get_size()
            self.render_size = render_size
            self.tiled_mode = self._should_tile(orientation)
            self._reset_tiled_resources()
            self.cursor = self._clamped_cursor(self.cursor, self.render_size)
        self._update_cursor(window.clock)
        if self.tiled_mode:
            self._render_tiled(window)
        else:
            self.shader_runtime.render(
                window,
                uniforms=self._shader_uniforms(),
                viewport_size=self.render_size,
            )

    def reset(self) -> None:
        self._reset_tiled_resources()
        self.shader_runtime.reset()
        self.window_size = None
        self.render_size = None
        self.tiled_mode = False
        self.cursor = np.zeros((2,), dtype=np.float32)
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self.initialized = False
        super().reset()

    def _initialize_shader(self) -> None:
        template_path = Path(shader_template_location).parent
        self.shader_runtime.initialize(fragment_path=template_path / "frag.glsl")

    def _shader_uniforms(
        self,
        viewport_origin: tuple[int, int] = (0, 0),
    ) -> dict[str, UniformValue]:
        assert self.render_size is not None
        return {
            "iResolution": self.render_size,
            "iMouse": self.cursor,
            "iMouseScale": MOUSE_SCALE,
            "iViewportOrigin": viewport_origin,
            "iTime": time.monotonic() - self.state.start_time,
        }

    def _update_cursor(self, clock: pygame.time.Clock | None) -> None:
        assert self.render_size is not None
        direction = self._cursor_direction()
        if direction[0] == 0.0 and direction[1] == 0.0:
            return
        elapsed_s = self._elapsed_seconds(clock)
        self.cursor = self._clamped_cursor(
            self.cursor + direction * CURSOR_SPEED_PX_PER_SECOND * elapsed_s,
            self.render_size,
        )

    def _render_tiled(self, window: DisplayContext) -> None:
        assert self.render_size is not None
        assert self.window_size is not None
        self._ensure_tiled_resources()
        assert self.tile_pixels is not None
        assert self.display_texture is not None

        tile_width, tile_height = self.render_size
        self.shader_runtime.draw(
            uniforms=self._shader_uniforms(),
            viewport_size=self.render_size,
        )
        glReadPixels(
            0,
            0,
            tile_width,
            tile_height,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.tile_pixels,
        )
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexSubImage2D(
            GL_TEXTURE_2D,
            0,
            0,
            0,
            tile_width,
            tile_height,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.tile_pixels,
        )
        self._render_tiled_texture()
        self.shader_runtime.read_to_surface(window, size=self.window_size)

    def _ensure_tiled_resources(self) -> None:
        assert self.render_size is not None
        width, height = self.render_size
        if (
            self.tile_pixels is None
            or self.tile_pixels.shape[0] != height
            or self.tile_pixels.shape[1] != width
        ):
            self.tile_pixels = np.zeros((height, width, 4), dtype=np.uint8)
        if self.display_texture is not None:
            return
        self.display_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            width,
            height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )

    def _render_tiled_texture(self) -> None:
        assert self.display_texture is not None
        assert self.render_size is not None
        assert self.window_size is not None
        tile_width, tile_height = self.render_size
        glViewport(0, 0, self.window_size[0], self.window_size[1])
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.window_size[0], 0, self.window_size[1], -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glUseProgram(0)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        for x in range(0, self.window_size[0], tile_width):
            for y in range(0, self.window_size[1], tile_height):
                glBegin(GL_QUADS)
                glTexCoord2f(0, 0)
                glVertex2f(x, y)
                glTexCoord2f(1, 0)
                glVertex2f(x + tile_width, y)
                glTexCoord2f(1, 1)
                glVertex2f(x + tile_width, y + tile_height)
                glTexCoord2f(0, 1)
                glVertex2f(x, y + tile_height)
                glEnd()
        glDisable(GL_TEXTURE_2D)

    def _reset_tiled_resources(self) -> None:
        if self.display_texture is not None:
            try:
                glDeleteTextures([self.display_texture])
            except GLError:
                pass
        self.display_texture = None
        self.tile_pixels = None

    def _cursor_direction(self) -> np.ndarray:
        keys = self._keyboard_snapshot.pressed_keys
        direction = np.array(
            [
                float(pygame.K_d in keys or pygame.K_RIGHT in keys)
                - float(pygame.K_a in keys or pygame.K_LEFT in keys),
                float(pygame.K_w in keys or pygame.K_UP in keys)
                - float(pygame.K_s in keys or pygame.K_DOWN in keys),
            ],
            dtype=np.float32,
        )
        for event in self._gamepad_snapshots:
            snapshot = event.snapshot
            direction[0] += snapshot.dpad.x
            direction[1] += snapshot.dpad.y
            direction[0] += snapshot.axis_value(
                GamepadAxis.LEFT_X,
                dead_zone=GAMEPAD_DEAD_ZONE,
            )
            direction[1] -= snapshot.axis_value(
                GamepadAxis.LEFT_Y,
                dead_zone=GAMEPAD_DEAD_ZONE,
            )
        if np.linalg.norm(direction) > 1.0:
            direction = direction / np.linalg.norm(direction)
        if (
            pygame.K_LSHIFT in keys
            or pygame.K_RSHIFT in keys
            or any(
                event.snapshot.button_held(GamepadButton.EAST)
                for event in self._gamepad_snapshots
            )
        ):
            direction *= KEYBOARD_FAST_MULTIPLIER
        return direction

    def _set_keyboard_snapshot(self, snapshot: KeyboardSnapshot) -> None:
        self._keyboard_snapshot = snapshot

    def _refresh_keyboard_snapshot(self) -> None:
        self._keyboard_snapshot = (
            self.state.peripheral_manager.input_io.controls.keyboard()
        )

    def _refresh_gamepad_snapshot(self) -> None:
        self._gamepad_snapshots = (
            self.state.peripheral_manager.input_io.controls.gamepads()
        )

    @staticmethod
    def _elapsed_seconds(clock: pygame.time.Clock | None) -> float:
        if clock is None:
            return 1.0 / 60.0
        elapsed_s = clock.get_time() / 1000.0
        if elapsed_s <= 0.0:
            return 1.0 / 60.0
        return min(elapsed_s, 0.1)

    @staticmethod
    def _initial_cursor(window_size: tuple[int, int]) -> np.ndarray:
        width, height = window_size
        return np.array((width * 0.68, height * 0.62), dtype=np.float32)

    @staticmethod
    def _render_size(
        window_size: tuple[int, int],
        orientation: Orientation,
    ) -> tuple[int, int]:
        if PaletteTunnelScene._should_tile(orientation):
            layout = orientation.layout
            return (
                max(1, window_size[0] // layout.columns),
                max(1, window_size[1] // layout.rows),
            )
        return window_size

    @staticmethod
    def _should_tile(orientation: Orientation) -> bool:
        layout = orientation.layout
        return layout.columns > 1 or layout.rows > 1

    @staticmethod
    def _clamped_cursor(
        cursor: np.ndarray,
        window_size: tuple[int, int],
    ) -> np.ndarray:
        width, height = window_size
        return np.array(
            (
                min(max(float(cursor[0]), 0.0), float(width)),
                min(max(float(cursor[1]), 0.0), float(height)),
            ),
            dtype=np.float32,
        )

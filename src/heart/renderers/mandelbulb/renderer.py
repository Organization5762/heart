from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame
from manyfold.graph import SubscriptionLike
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
from heart.device import Cube, Orientation
from heart.display.shaders.fullscreen import (FullscreenShaderRuntime,
                                              UniformValue)
from heart.display.shaders.shader_templates.mandelbulb import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

GAMEPAD_DEAD_ZONE = 0.12
ORBIT_RADIANS_PER_SECOND = 1.4
ZOOM_UNITS_PER_SECOND = 1.4
COLOR_PHASE_PER_SECOND = 1.2
COLOR_VECTOR_EASE_PER_SECOND = 12.0
POWER_EASE_PER_SECOND = 8.0
DEFAULT_CAMERA_DISTANCE = 3.0
MIN_CAMERA_DISTANCE = 1.8
MAX_CAMERA_DISTANCE = 6.0
MIN_CAMERA_PITCH = -1.1
MAX_CAMERA_PITCH = 1.1
BASE_POWER = 6.0
MIN_POWER = 1.0
MAX_POWER = 12.0
POWER_UNITS_PER_SECOND = 1.0
MORPH_POWER_DELTA = 2.0
MORPH_EASE_PER_SECOND = 18.0


@dataclass
class MandelbulbState:
    start_time: float


class MandelbulbScene(StatefulBaseRenderer[MandelbulbState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.shader_runtime = FullscreenShaderRuntime()
        self.window_size: tuple[int, int] | None = None
        self.render_size: tuple[int, int] | None = None
        self.tiled_mode = False
        self.display_texture: int | None = None
        self.tile_pixels: np.ndarray | None = None
        self.camera_yaw = 0.0
        self.camera_pitch = 0.0
        self.camera_distance = DEFAULT_CAMERA_DISTANCE
        self.power = BASE_POWER
        self.target_power = BASE_POWER
        self.morph_target_power = self._wrapped_power(BASE_POWER + MORPH_POWER_DELTA)
        self.color_phase = 0.0
        self.color_vector = np.zeros((2,), dtype=np.float32)
        self.phase_shift_enabled = True
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._key_pressed_last_frame: dict[int, bool] = {}
        self._subscriptions: list[SubscriptionLike] = []

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
    ) -> MandelbulbState:
        self.window_size = window.get_size()
        self.render_size = self._render_size(self.window_size, orientation)
        self.tiled_mode = isinstance(orientation, Cube)
        self._initialize_shader()
        self._subscriptions = [
            peripheral_manager.keyboard_controller.snapshot_stream().subscribe(
                on_next=self._set_keyboard_snapshot,
            ),
            peripheral_manager.gamepad_controller.snapshot_stream().subscribe(
                on_next=self._set_gamepad_snapshot,
            ),
        ]
        return MandelbulbState(start_time=time.monotonic())

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        render_size = self._render_size(window.get_size(), orientation)
        if self.window_size != window.get_size() or self.render_size != render_size:
            self.window_size = window.get_size()
            self.render_size = render_size
            self.tiled_mode = isinstance(orientation, Cube)
            self._reset_tiled_resources()

        self._process_input(window.clock)

        if self.tiled_mode:
            self._render_tiled(window)
            return

        self.shader_runtime.render(
            window,
            uniforms=self._shader_uniforms(),
            viewport_size=self.render_size,
        )

    def reset(self) -> None:
        for subscription in self._subscriptions:
            subscription.dispose()
        self._subscriptions.clear()
        self._reset_tiled_resources()
        self.shader_runtime.reset()
        self.window_size = None
        self.render_size = None
        self.tiled_mode = False
        self.camera_yaw = 0.0
        self.camera_pitch = 0.0
        self.camera_distance = DEFAULT_CAMERA_DISTANCE
        self.power = BASE_POWER
        self.target_power = BASE_POWER
        self.morph_target_power = self._wrapped_power(BASE_POWER + MORPH_POWER_DELTA)
        self.color_phase = 0.0
        self.color_vector = np.zeros((2,), dtype=np.float32)
        self.phase_shift_enabled = True
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._key_pressed_last_frame.clear()
        self.initialized = False
        super().reset()

    def _initialize_shader(self) -> None:
        template_path = Path(shader_template_location).parent
        self.shader_runtime.initialize(fragment_path=template_path / "frag.glsl")

    def _shader_uniforms(self) -> dict[str, UniformValue]:
        assert self.render_size is not None
        return {
            "iResolution": self.render_size,
            "iTime": time.monotonic() - self.state.start_time,
            "uCameraYaw": self.camera_yaw,
            "uCameraPitch": self.camera_pitch,
            "uCameraDistance": self.camera_distance,
            "uPower": self.power,
            "uColorPhase": self.color_phase,
            "uColorVector": self.color_vector,
            "uPhaseShift": float(self.phase_shift_enabled),
        }

    def _process_input(self, clock: pygame.time.Clock | None) -> None:
        elapsed_s = self._elapsed_seconds(clock)
        keys = self._keyboard_snapshot.pressed_keys
        orbit_x = (
            float(pygame.K_RIGHT in keys)
            - float(pygame.K_LEFT in keys)
            + self._gamepad_snapshot.axis_value(
                GamepadAxis.LEFT_X,
                dead_zone=GAMEPAD_DEAD_ZONE,
            )
        )
        orbit_y = (
            float(pygame.K_UP in keys)
            - float(pygame.K_DOWN in keys)
            - self._gamepad_snapshot.axis_value(
                GamepadAxis.LEFT_Y,
                dead_zone=GAMEPAD_DEAD_ZONE,
            )
        )
        self.camera_yaw += orbit_x * ORBIT_RADIANS_PER_SECOND * elapsed_s
        self.camera_pitch = self._clamp(
            self.camera_pitch + orbit_y * ORBIT_RADIANS_PER_SECOND * elapsed_s,
            MIN_CAMERA_PITCH,
            MAX_CAMERA_PITCH,
        )

        zoom = (
            float(pygame.K_s in keys)
            - float(pygame.K_w in keys)
        )
        if self._gamepad_snapshot.button_held(GamepadButton.MINUS):
            zoom += 1.0
        if self._gamepad_snapshot.button_held(GamepadButton.PLUS):
            zoom -= 1.0
        self.camera_distance = self._clamp(
            self.camera_distance + zoom * ZOOM_UNITS_PER_SECOND * elapsed_s,
            MIN_CAMERA_DISTANCE,
            MAX_CAMERA_DISTANCE,
        )

        power_delta = (
            -float(pygame.K_LSHIFT in keys or pygame.K_RSHIFT in keys)
            + self._gamepad_snapshot.axis_value(
                GamepadAxis.TRIGGER_RIGHT,
                dead_zone=0.0,
            )
            - self._gamepad_snapshot.axis_value(
                GamepadAxis.TRIGGER_LEFT,
                dead_zone=0.0,
            )
        )
        if self._gamepad_snapshot.button_held(GamepadButton.EAST):
            power_delta -= 1.0
        self.target_power = self._clamp(
            self.target_power + power_delta * POWER_UNITS_PER_SECOND * elapsed_s,
            MIN_POWER,
            MAX_POWER,
        )
        self.morph_target_power = self._wrapped_power(
            self.target_power + MORPH_POWER_DELTA
        )
        morph_held = self._power_morph_held(keys)
        rendered_target_power = self.morph_target_power if morph_held else self.target_power
        ease = MORPH_EASE_PER_SECOND if morph_held else POWER_EASE_PER_SECOND
        lerp_weight = 1.0 - np.exp(-ease * elapsed_s)
        self.power = float(self.power + (rendered_target_power - self.power) * lerp_weight)

        color_scrub = (
            float(pygame.K_d in keys)
            - float(pygame.K_a in keys)
        )
        self.color_phase += color_scrub * COLOR_PHASE_PER_SECOND * elapsed_s
        self._update_color_vector(elapsed_s)

        if self._phase_toggle_tapped(keys):
            self.phase_shift_enabled = not self.phase_shift_enabled

    def _update_color_vector(self, elapsed_s: float) -> None:
        raw_vector = np.array(
            [
                self._gamepad_snapshot.axis_value(
                    GamepadAxis.RIGHT_X,
                    dead_zone=GAMEPAD_DEAD_ZONE,
                ),
                -self._gamepad_snapshot.axis_value(
                    GamepadAxis.RIGHT_Y,
                    dead_zone=GAMEPAD_DEAD_ZONE,
                ),
            ],
            dtype=np.float32,
        )
        magnitude = float(np.linalg.norm(raw_vector))
        if magnitude <= 0.0:
            return
        if magnitude > 1.0:
            raw_vector = raw_vector / magnitude
        lerp_weight = 1.0 - np.exp(-COLOR_VECTOR_EASE_PER_SECOND * elapsed_s)
        self.color_vector = (
            self.color_vector + (raw_vector - self.color_vector) * lerp_weight
        ).astype(np.float32)

    def _phase_toggle_tapped(self, keys: frozenset[int]) -> bool:
        keyboard_pressed = pygame.K_c in keys
        keyboard_tapped = keyboard_pressed and not self._key_pressed_last_frame.get(
            pygame.K_c,
            False,
        )
        self._key_pressed_last_frame[pygame.K_c] = keyboard_pressed
        return keyboard_tapped or self._gamepad_snapshot.button_tapped(GamepadButton.WEST)

    def _set_keyboard_snapshot(self, snapshot: KeyboardSnapshot) -> None:
        self._keyboard_snapshot = snapshot

    def _set_gamepad_snapshot(self, snapshot: GamepadSnapshot) -> None:
        self._gamepad_snapshot = snapshot

    def _power_morph_held(self, keys: frozenset[int]) -> bool:
        return pygame.K_SPACE in keys or self._gamepad_snapshot.button_held(
            GamepadButton.SOUTH
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

    @staticmethod
    def _render_size(
        window_size: tuple[int, int],
        orientation: Orientation,
    ) -> tuple[int, int]:
        if isinstance(orientation, Cube):
            return (window_size[1], window_size[1])
        return window_size

    @staticmethod
    def _elapsed_seconds(clock: pygame.time.Clock | None) -> float:
        if clock is None:
            return 1.0 / 60.0
        elapsed_s = clock.get_time() / 1000.0
        if elapsed_s <= 0.0:
            return 1.0 / 60.0
        return min(elapsed_s, 0.1)

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return min(max(value, low), high)

    @staticmethod
    def _wrapped_power(value: float) -> float:
        span = MAX_POWER - MIN_POWER
        if span <= 0.0:
            return MIN_POWER
        return ((value - MIN_POWER) % span) + MIN_POWER

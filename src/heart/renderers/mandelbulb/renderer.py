from __future__ import annotations

import argparse
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
from heart.device import Cube, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.display.shaders.fullscreen import (FullscreenShaderRuntime,
                                              UniformValue)
from heart.display.shaders.shader_templates.mandelbulb import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
DEFAULT_DEBUG_WIDTH = 2048
DEFAULT_DEBUG_HEIGHT = 1200
DEFAULT_DEBUG_FPS = 60
DEFAULT_DEBUG_LAYOUT = "rectangle"
GAMEPAD_DEAD_ZONE = 0.12
ORBIT_RADIANS_PER_SECOND = 1.4
AUTO_ORBIT_RADIANS_PER_SECOND = 0.12
ZOOM_UNITS_PER_SECOND = 1.4
COLOR_PHASE_PER_SECOND = 1.2
COLOR_VECTOR_EASE_PER_SECOND = 12.0
DEFAULT_COLOR_MODE = 1
COLOR_MODE_COUNT = 4
BASE_PHASE_SPEED = 1.0
MIN_PHASE_SPEED = 0.1
MAX_PHASE_SPEED = 8.0
PHASE_SPEED_UNITS_PER_SECOND = 1.5
POWER_EASE_PER_SECOND = 8.0
DEFAULT_CAMERA_DISTANCE = 3.0
MIN_CAMERA_DISTANCE = 2.2
MAX_CAMERA_DISTANCE = 6.0
MIN_CAMERA_PITCH = -1.1
MAX_CAMERA_PITCH = 1.1
BASE_POWER = 4.0
MIN_POWER = 1.0
MAX_POWER = 12.0
POWER_UNITS_PER_SECOND = 0.9
MORPH_POWER_DELTA = 2.0
MORPH_EASE_PER_SECOND = 18.0


@dataclass
class MandelbulbState:
    start_time: float
    peripheral_manager: PeripheralManager


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
        self.color_mode = DEFAULT_COLOR_MODE
        self.phase_time = 0.0
        self.phase_speed = BASE_PHASE_SPEED
        self.phase_shift_enabled = True
        self.auto_orbit_yaw = 0.0
        self.auto_orbit_enabled = True
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots: tuple[GamepadSnapshotEvent, ...] = ()
        self._key_pressed_last_frame: dict[int, bool] = {}
        self._last_phase_toggle_snapshot_time: float | None = None
        self._last_auto_orbit_toggle_snapshot_time: float | None = None
        self._last_color_mode_toggle_snapshot_time: float | None = None

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
        self.tiled_mode = self._should_tile(orientation)
        self._initialize_shader()
        return MandelbulbState(
            start_time=time.monotonic(),
            peripheral_manager=peripheral_manager,
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        render_size = self._render_size(window.get_size(), orientation)
        if self.window_size != window.get_size() or self.render_size != render_size:
            self.window_size = window.get_size()
            self.render_size = render_size
            self.tiled_mode = self._should_tile(orientation)
            self._reset_tiled_resources()

        self._refresh_keyboard_snapshot()
        self._refresh_gamepad_snapshot()
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
        self.color_mode = DEFAULT_COLOR_MODE
        self.phase_time = 0.0
        self.phase_speed = BASE_PHASE_SPEED
        self.phase_shift_enabled = True
        self.auto_orbit_yaw = 0.0
        self.auto_orbit_enabled = True
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots = ()
        self._key_pressed_last_frame.clear()
        self._last_phase_toggle_snapshot_time = None
        self._last_auto_orbit_toggle_snapshot_time = None
        self._last_color_mode_toggle_snapshot_time = None
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
            "uColorMode": float(self.color_mode),
            "uPhaseTime": self.phase_time,
            "uAutoYaw": self.auto_orbit_yaw,
        }

    def _process_input(self, clock: pygame.time.Clock | None) -> None:
        elapsed_s = self._elapsed_seconds(clock)
        keys = self._keyboard_snapshot.pressed_keys
        self._process_toggles(keys)
        phase_speed_delta = float(self._button_held(GamepadButton.PLUS)) - float(
            self._button_held(GamepadButton.MINUS)
        )
        self.phase_speed = self._clamp(
            self.phase_speed
            + phase_speed_delta * PHASE_SPEED_UNITS_PER_SECOND * elapsed_s,
            MIN_PHASE_SPEED,
            MAX_PHASE_SPEED,
        )
        if self.phase_shift_enabled:
            self.phase_time += elapsed_s * self.phase_speed
        if self.auto_orbit_enabled:
            self.auto_orbit_yaw += AUTO_ORBIT_RADIANS_PER_SECOND * elapsed_s

        orbit_x = (
            float(pygame.K_RIGHT in keys)
            - float(pygame.K_LEFT in keys)
            + self._axis_value(
                GamepadAxis.LEFT_X,
                dead_zone=GAMEPAD_DEAD_ZONE,
            )
        )
        orbit_y = (
            float(pygame.K_UP in keys)
            - float(pygame.K_DOWN in keys)
            - self._axis_value(
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

        zoom = float(pygame.K_s in keys) - float(pygame.K_w in keys)
        if self._button_held(GamepadButton.ZL):
            zoom += 1.0
        if self._button_held(GamepadButton.ZR):
            zoom -= 1.0
        self.camera_distance = self._clamp(
            self.camera_distance + zoom * ZOOM_UNITS_PER_SECOND * elapsed_s,
            MIN_CAMERA_DISTANCE,
            MAX_CAMERA_DISTANCE,
        )

        trigger_right = self._trigger_pressure(GamepadAxis.TRIGGER_RIGHT)
        trigger_left = self._trigger_pressure(GamepadAxis.TRIGGER_LEFT)
        power_delta = (
            -float(pygame.K_LSHIFT in keys or pygame.K_RSHIFT in keys)
            + trigger_right
            - trigger_left
        )
        if self._button_held(GamepadButton.EAST):
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
        rendered_target_power = (
            self.morph_target_power if morph_held else self.target_power
        )
        ease = MORPH_EASE_PER_SECOND if morph_held else POWER_EASE_PER_SECOND
        lerp_weight = 1.0 - np.exp(-ease * elapsed_s)
        self.power = float(
            self.power + (rendered_target_power - self.power) * lerp_weight
        )

        color_scrub = float(pygame.K_d in keys) - float(pygame.K_a in keys)
        self.color_phase += color_scrub * COLOR_PHASE_PER_SECOND * elapsed_s
        self._update_color_vector(elapsed_s)

    def _process_toggles(self, keys: frozenset[int]) -> None:
        if self._phase_toggle_tapped(keys):
            self.phase_shift_enabled = not self.phase_shift_enabled
        if self._auto_orbit_toggle_tapped(keys):
            self.auto_orbit_enabled = not self.auto_orbit_enabled
        if self._color_mode_toggle_tapped():
            self.color_mode = (self.color_mode + 1) % COLOR_MODE_COUNT

    def _update_color_vector(self, elapsed_s: float) -> None:
        raw_vector = np.array(
            [
                self._axis_value(
                    GamepadAxis.RIGHT_X,
                    dead_zone=GAMEPAD_DEAD_ZONE,
                ),
                -self._axis_value(
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
        gamepad_tapped = self._gamepad_tapped_once(
            button=GamepadButton.WEST,
            last_timestamp=self._last_phase_toggle_snapshot_time,
        )
        if gamepad_tapped:
            self._last_phase_toggle_snapshot_time = self._latest_tapped_timestamp(
                GamepadButton.WEST
            )
        return keyboard_tapped or gamepad_tapped

    def _auto_orbit_toggle_tapped(self, keys: frozenset[int]) -> bool:
        keyboard_pressed = pygame.K_o in keys
        keyboard_tapped = keyboard_pressed and not self._key_pressed_last_frame.get(
            pygame.K_o,
            False,
        )
        self._key_pressed_last_frame[pygame.K_o] = keyboard_pressed
        gamepad_tapped = self._gamepad_tapped_once(
            button=GamepadButton.L3,
            last_timestamp=self._last_auto_orbit_toggle_snapshot_time,
        )
        if gamepad_tapped:
            self._last_auto_orbit_toggle_snapshot_time = self._latest_tapped_timestamp(
                GamepadButton.L3
            )
        return keyboard_tapped or gamepad_tapped

    def _color_mode_toggle_tapped(self) -> bool:
        gamepad_tapped = self._gamepad_tapped_once(
            button=GamepadButton.R3,
            last_timestamp=self._last_color_mode_toggle_snapshot_time,
        )
        if gamepad_tapped:
            self._last_color_mode_toggle_snapshot_time = self._latest_tapped_timestamp(
                GamepadButton.R3
            )
        return gamepad_tapped

    def _gamepad_tapped_once(
        self,
        *,
        button: GamepadButton,
        last_timestamp: float | None,
    ) -> bool:
        timestamp = self._latest_tapped_timestamp(button)
        return timestamp is not None and timestamp != last_timestamp

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

    def _power_morph_held(self, keys: frozenset[int]) -> bool:
        return pygame.K_SPACE in keys or self._button_held(GamepadButton.SOUTH)

    def _trigger_pressure(self, axis: GamepadAxis) -> float:
        raw_value = self._axis_value(axis, dead_zone=0.0)
        if raw_value < 0.0:
            return self._clamp((raw_value + 1.0) * 0.5, 0.0, 1.0)
        return self._clamp(raw_value, 0.0, 1.0)

    def _button_held(self, button: GamepadButton) -> bool:
        return any(
            event.snapshot.button_held(button) for event in self._gamepad_snapshots
        )

    def _axis_value(self, axis: GamepadAxis, *, dead_zone: float) -> float:
        values = [
            event.snapshot.axis_value(axis, dead_zone=dead_zone)
            for event in self._gamepad_snapshots
        ]
        if not values:
            return 0.0
        if axis in {GamepadAxis.TRIGGER_LEFT, GamepadAxis.TRIGGER_RIGHT}:
            return max(values)
        return max(values, key=abs)

    def _latest_tapped_timestamp(self, button: GamepadButton) -> float | None:
        timestamps = [
            event.snapshot.timestamp_monotonic
            for event in self._gamepad_snapshots
            if event.snapshot.button_tapped(button)
        ]
        if not timestamps:
            return None
        return max(timestamps)

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
        if MandelbulbScene._should_tile(orientation):
            layout = orientation.layout
            return (
                max(1, window_size[0] // layout.columns),
                max(1, window_size[1] // layout.rows),
            )
        return window_size

    @staticmethod
    def _should_tile(orientation: Orientation) -> bool:
        layout = getattr(orientation, "layout", None)
        if layout is None:
            return False
        columns = getattr(layout, "columns", 1)
        rows = getattr(layout, "rows", 1)
        if not isinstance(columns, int) or not isinstance(rows, int):
            return False
        return columns > 1 or rows > 1

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Mandelbulb renderer directly in a local debug window.",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=DEFAULT_DEBUG_WIDTH,
        help="Window width in pixels.",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_DEBUG_HEIGHT,
        help="Window height in pixels.",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=DEFAULT_DEBUG_FPS,
        help="Frame cap for the debug loop.",
    )
    parser.add_argument(
        "--layout",
        choices=(DEFAULT_DEBUG_LAYOUT, "cube"),
        default=DEFAULT_DEBUG_LAYOUT,
        help="Render as a single rectangle or use the cube tiling path.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    orientation = (
        Cube.sides()
        if args.layout == "cube"
        else Rectangle.with_layout(columns=1, rows=1)
    )

    device = LocalScreen(width=args.width, height=args.height, orientation=orientation)
    container = build_runtime_container(device=device)
    peripheral_manager = container.resolve(PeripheralManager)
    peripheral_runtime = container.resolve(PeripheralRuntime)
    display = container.resolve(DisplayContext)
    scene = MandelbulbScene()

    logger.info(
        "Starting standalone Mandelbulb debug window width=%s height=%s layout=%s fps=%s",
        args.width,
        args.height,
        args.layout,
        args.fps,
    )

    display.initialize()
    display.configure_window(DeviceDisplayMode.OPENGL)
    peripheral_manager.detect()
    peripheral_manager.start()

    running = True
    try:
        scene.initialize(
            window=display,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    running = False
            peripheral_runtime.tick()
            scene.real_process(window=display, orientation=orientation)
            pygame.display.flip()
            if display.clock is None:
                raise RuntimeError(
                    "Standalone Mandelbulb debug loop did not initialize a clock"
                )
            display.clock.tick(args.fps)
            peripheral_runtime.tick()
        scene.reset()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

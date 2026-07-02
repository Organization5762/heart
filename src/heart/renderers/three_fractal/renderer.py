import argparse
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pygame
from manyfold import StreamNode
from OpenGL.error import GLError
from OpenGL.GL import (GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_MODELVIEW,
                       GL_NEAREST, GL_PROJECTION, GL_QUADS, GL_RENDERER,
                       GL_RGBA, GL_SHADING_LANGUAGE_VERSION, GL_TEXTURE_2D,
                       GL_TEXTURE_MAG_FILTER, GL_TEXTURE_MIN_FILTER,
                       GL_UNSIGNED_BYTE, GL_VENDOR, GL_VERSION, glBegin,
                       glBindTexture, glClear, glDeleteTextures, glDisable,
                       glEnable, glEnd, glGenTextures, glGetString,
                       glLoadIdentity, glMatrixMode, glOrtho, glReadPixels,
                       glTexCoord2f, glTexImage2D, glTexParameteri,
                       glTexSubImage2D, glUseProgram, glVertex2f, glViewport)
from pygame.math import lerp

from heart import DeviceDisplayMode
from heart.device import Cube, Orientation, Rectangle
from heart.device.local import LocalScreen
from heart.display.shaders.fullscreen import (FullscreenShaderRuntime,
                                              UniformValue)
from heart.display.shaders.shader_templates.three_fractal import \
    __file__ as shader_template_location
from heart.peripheral.core.input import (GamepadAxis, GamepadButton,
                                         GamepadDpadValue, GamepadSnapshot,
                                         GamepadSnapshotEvent,
                                         KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.three_fractal.provider import FractalSceneProvider
from heart.renderers.three_fractal.state import FractalSceneState
from heart.runtime.container import build_runtime_container
from heart.runtime.display_context import DisplayContext
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
DEFAULT_DEBUG_WIDTH = 800
DEFAULT_DEBUG_HEIGHT = 800
DEFAULT_DEBUG_FPS = 60
DEFAULT_DEBUG_LAYOUT = "rectangle"
TRIGGER_ACTIVE_THRESHOLD = 0.5


def _opengl_string(name: int, label: str) -> str:
    try:
        value = glGetString(name)
    except GLError as exc:
        logger.warning("Unable to read OpenGL %s: %s", label, exc)
        return "unavailable"
    if value is None:
        return "unavailable"
    return value.decode("utf-8", errors="replace")


@dataclass
class FractalRuntimeState:
    peripheral_manager: PeripheralManager


class FractalRuntime(StatefulBaseRenderer[FractalRuntimeState]):
    def __init__(self, device=None):
        super().__init__()
        self.device = device

        # Set to OPENGL to have your framework detect it properly
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self._initialized = False
        self.mat = None
        self.vel = np.zeros((3,), dtype=np.float32)
        self.look_x = 0.0
        self.look_y = 0.0
        self.look_speed = 0.003
        self.speed_accel = 2.0
        self.speed_decel = 0.6
        self.max_fps = 60

        self.max_velocity = 2.0

        self.prevMat = None

        self.window_size = None
        self.program = None
        self.sphere_radius_uniform_var = "S_RADIUS"
        self.last_update_time = None
        self.sign = 1

        self.variable_bindings = {}
        self.sphere_radius_var = "s_radius"
        self.BASE_RADIUS = 0.5
        self._LO_BASE = self.BASE_RADIUS
        self._HI_BASE = 1.2
        self.active_radius = self.BASE_RADIUS

        self.shader_runtime = FullscreenShaderRuntime()

        self.last_frame_time = None
        self.delta_real_time = None
        self.virtual_time = 0
        self.INFLATE_SPEED = 10
        self.look_speed = 0.003
        self.key_pressed_last_frame: dict = {}
        self.screen_center = None

        self.prev_mouse_pos = None
        self.mouse_pos = None
        self.clock = None
        self.fbo = None
        self.tiled_mode = False
        self.last_fps_print = 0
        self.AMPLITUDE = 0.05
        self.PULSE_FREQUENCY = 3.0
        self.render_size = None
        self.real_window_size = None

        # For rendering to the provided surface
        self.target_surface = None
        self.display_texture = None
        self.pixels = None
        self.surface_array = None

        self.initialized = False
        self.time_initialized = None
        self._auto_started = False
        self._keyboard_snapshot = KeyboardSnapshot(
            pressed_keys=frozenset(),
            timestamp_ms=0.0,
        )
        self._gamepad_snapshot = GamepadSnapshot(connected=False, identifier=None)
        self._gamepad_snapshots: tuple[GamepadSnapshotEvent, ...] = ()
        self._trigger_right_prev_active = False

    def is_initialized(self) -> bool:
        if not super().is_initialized():
            return False
        if (
            self.shader is None
            or self.program is None
            or not self.shader_runtime.is_initialized()
            or self.clock is None
            or self.mat is None
            or self.prevMat is None
            or self.window_size is None
            or self.surface_array is None
        ):
            return False
        if self.tiled_mode and (
            self.render_size is None
            or self.real_window_size is None
            or getattr(self, "pixels", None) is None
            or getattr(self, "display_texture", None) is None
        ):
            return False
        return True

    @property
    def shader(self) -> FullscreenShaderRuntime | None:
        if self.shader_runtime.is_initialized():
            return self.shader_runtime
        return None

    @shader.setter
    def shader(self, value) -> None:
        if value is None:
            self.shader_runtime.reset()

    def _shader_uniforms(self) -> dict[str, UniformValue]:
        return {
            "iMat": self.mat,
            "iPrevMat": self.prevMat,
            "iResolution": self.window_size,
            "iIPD": 0.04,
            "_s_radius": self.active_radius,
        }

    def _render(self):
        template_path = Path(shader_template_location).parent
        self.shader_runtime.initialize(
            vertex_path=template_path / "vert.glsl",
            fragment_path=template_path / "frag_gen.glsl",
            attribute_name="vPosition",
        )
        self.program = self.shader_runtime.program
        logger.info("Compiled shader.")

    # Modified initialize to use the provided window
    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FractalRuntimeState:
        """Initialize the fractal renderer with the given window size."""
        logger.info(
            "OpenGL Version: %s",
            _opengl_string(GL_VERSION, "version"),
        )
        logger.info(
            "OpenGL Vendor: %s",
            _opengl_string(GL_VENDOR, "vendor"),
        )
        logger.info(
            "OpenGL Renderer: %s",
            _opengl_string(GL_RENDERER, "renderer"),
        )
        logger.info(
            "OpenGL Shading Language Version: %s",
            _opengl_string(GL_SHADING_LANGUAGE_VERSION, "shading language version"),
        )

        self.time_initialized = time.monotonic()
        self.target_surface = window
        window_size = window.get_size()
        tiled_mode = self._should_tile(orientation)

        self.tiled_mode = tiled_mode
        self.clock = window.clock
        self.mode = "auto"

        if self.tiled_mode:
            self.render_size = self._tile_render_size(window_size, orientation)
            self.window_size = self.render_size
            self.real_window_size = window_size

            # Create resources for tiled rendering
            self.setup_tiled_rendering()
        else:
            # For normal mode, use the actual window size
            self.window_size = window_size

        # Create buffer for capturing pixels
        self.surface_array = np.zeros(
            (window_size[1], window_size[0], 4), dtype=np.uint8
        )
        self.screen_center = (window_size[0] / 2, window_size[1] / 2)
        pygame.mouse.set_visible(False)
        self._center_mouse()

        # Create the fractal shader
        self._render()

        # Initialize camera matrices
        start_pos = [0, 0, 12.0]
        self.mat = np.identity(4, np.float32)
        self.mat[3, :3] = np.array(start_pos)
        self.prevMat = np.copy(self.mat)
        self.last_update_time = time.monotonic()

        self.last_frame_time = time.monotonic()
        return FractalRuntimeState(peripheral_manager=peripheral_manager)

        self.mode = "auto"

        # self.active_color = (1, 1, 1)

    def setup_tiled_rendering(self):
        """Set up resources for tiled rendering."""
        # Create a pixel buffer to store the rendered result
        self.pixels = np.zeros(
            (self.render_size[1], self.render_size[0], 4), dtype=np.uint8
        )

        # Create a texture to hold the rendered result for display
        self.display_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.render_size[0],
            self.render_size[1],
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            None,
        )

    def render_fractal(self):
        """Render the fractal scene."""
        assert self.program is not None
        assert self.window_size is not None
        self.shader_runtime.draw(
            uniforms=self._shader_uniforms(),
            viewport_size=self.window_size,
            clear_mask=None,
        )

    def render_to_surface(self):
        """Copy the OpenGL rendering to the Pygame surface."""
        size = self.real_window_size if self.tiled_mode else self.window_size
        self.shader_runtime.read_to_surface(self.target_surface, size=size)
        self.surface_array = self.shader_runtime.pixel_buffer

    def render_tiled(self):
        """Render the texture tiled across the screen."""
        # Set viewport back to the real window size
        glViewport(0, 0, self.real_window_size[0], self.real_window_size[1])

        # Set up orthographic projection for 2D drawing
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, self.real_window_size[0], 0, self.real_window_size[1], -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

        # Turn off the shader
        glUseProgram(0)

        # Enable texturing
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)

        # Draw the texture multiple times
        tile_width = self.render_size[0]
        tile_height = self.render_size[1]
        # Clear the screen for the tiled display
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        for x in range(0, self.real_window_size[0], tile_width):
            for y in range(0, self.real_window_size[1], tile_height):
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

        # Read pixels for rendering to Pygame surface
        glReadPixels(
            0,
            0,
            self.real_window_size[0],
            self.real_window_size[1],
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.surface_array,
        )

        # Clean up
        glDisable(GL_TEXTURE_2D)

    def _center_mouse(self):
        if pygame.key.get_focused():
            pygame.mouse.set_pos(self.screen_center)

    @staticmethod
    def reorthogonalize(mat):
        u, s, v = np.linalg.svd(mat)
        return np.dot(u, v)

    @staticmethod
    def make_rot(angle, axis_ix):
        s = math.sin(angle)
        c = math.cos(angle)
        if axis_ix == 0:
            return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float32)
        elif axis_ix == 1:
            return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float32)
        elif axis_ix == 2:
            return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float32)

    def _process_mouse(self):
        self.prev_mouse_pos = self.mouse_pos
        self.mouse_pos = pygame.mouse.get_pos()

        dx, dy = 0, 0
        if self.prev_mouse_pos is not None:
            self._center_mouse()
            time_rate = (self.clock.get_time() / 1000.0) / (1 / self.max_fps)
            dx = (self.mouse_pos[0] - self.screen_center[0]) * time_rate
            dy = (self.mouse_pos[1] - self.screen_center[1]) * time_rate

        if pygame.key.get_focused():
            rx = self.make_rot(dx * self.look_speed, 1)
            ry = self.make_rot(dy * self.look_speed, 0)

            self.mat[:3, :3] = np.dot(ry, np.dot(rx, self.mat[:3, :3]))
            self.mat[:3, :3] = self.reorthogonalize(self.mat[:3, :3])

    def _process_auto(self):
        if not self._auto_started:
            self._reset_camera_pos()

        self._auto_started = True

        # move forward
        self.virtual_time += self.delta_real_time * self.PULSE_FREQUENCY

        acc = np.zeros((3,), dtype=np.float32)
        acc[2] -= self.speed_accel / self.max_fps
        self.vel += np.dot(self.mat[:3, :3].T, acc)
        vel_ratio = min(self.max_velocity, 1e20) / (np.linalg.norm(self.vel) + 1e-12)
        if vel_ratio < 1.0:
            self.vel *= vel_ratio

        # roll left
        rz = self.make_rot(0.01, 2)
        self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])

        # xr_mov = 0.17124
        xr_mov = -0.3524
        yr_mov = 0.1524
        fps_scale_factor = (self.clock.get_time() / 1000.0) / (1 / self.max_fps)
        stick_scale_factor = 8
        dx = xr_mov * stick_scale_factor * fps_scale_factor
        dy = yr_mov * stick_scale_factor * fps_scale_factor

        rx = self.make_rot(dx * self.look_speed, 1)
        ry = self.make_rot(dy * self.look_speed, 0)

        self.mat[:3, :3] = np.dot(ry, np.dot(rx, self.mat[:3, :3]))
        self.mat[:3, :3] = self.reorthogonalize(self.mat[:3, :3])

    def _check_enter_auto(self, peripheral_manager: PeripheralManager) -> None:
        """Return from free-look to auto mode on an explicit operator action."""

        keyboard_toggle_pressed = self._is_key_down(pygame.K_y)
        keyboard_toggle_tapped = (
            keyboard_toggle_pressed
            and not self.key_pressed_last_frame.get(pygame.K_y, False)
        )
        self.key_pressed_last_frame[pygame.K_y] = keyboard_toggle_pressed

        if (
            keyboard_toggle_tapped
            or self._button_tapped(GamepadButton.WEST)
            or self._button_tapped(GamepadButton.NORTH)
        ):
            self.mode = "auto"
            self._auto_started = False
            self._reset_camera_pos()

    def _check_break_auto(self, peripheral_manager: PeripheralManager):
        # ignore break auto check at first to avoid inut overlap from scene
        # select mode
        if time.monotonic() - self.time_initialized < 0.3:
            return False
        if self._has_manual_input():
            self.mode = "free"
            return True
        return False

    def set_mode_free(self):
        self.mode = "free"

    def _process_input(self, peripheral_manager):
        try:
            self._refresh_gamepad_snapshot(peripheral_manager)
            self._process_controller_input(peripheral_manager)
        except Exception:  # i haven't actually seen it fail but just in case
            logger.debug("Skipping fractal controller input update", exc_info=True)

    def _process_controller_input(self, peripheral_manager):
        # Calculate acceleration based on key input
        acc = np.zeros((3,), dtype=np.float32)
        if self._is_key_down(pygame.K_a):
            acc[0] -= self.speed_accel / self.max_fps
        if self._is_key_down(pygame.K_d):
            acc[0] += self.speed_accel / self.max_fps
        if self._is_key_down(pygame.K_w):
            acc[2] -= self.speed_accel / self.max_fps
        if self._is_key_down(pygame.K_s):
            acc[2] += self.speed_accel / self.max_fps

        acc[0] += (
            self._axis_value(GamepadAxis.LEFT_X, dead_zone=0.1)
            * self.speed_accel
            / self.max_fps
        )
        acc[2] += (
            self._axis_value(GamepadAxis.LEFT_Y, dead_zone=0.1)
            * self.speed_accel
            / self.max_fps
        )
        dpad = self._dpad_value()
        acc[0] += dpad.x * self.speed_accel / self.max_fps
        acc[2] -= dpad.y * self.speed_accel / self.max_fps

        # Apply acceleration or deceleration
        if np.isclose(np.dot(acc, acc), 0.0):
            self.vel *= self.speed_decel
        else:
            # Calculate desired direction
            direction = np.dot(self.mat[:3, :3].T, acc)
            direction_norm = np.linalg.norm(direction)

            if direction_norm > 0:
                # Normalize direction and scale by max_velocity
                normalized_direction = direction / direction_norm
                target_velocity = normalized_direction * self.max_velocity

                # Smoothly interpolate current velocity toward target
                lerp_factor = 0.1  # Adjust for faster/slower response
                self.vel = self.vel * (1 - lerp_factor) + target_velocity * lerp_factor

        trigger_right_active = (
            _trigger_pressure(
                self._axis_value(
                    GamepadAxis.TRIGGER_RIGHT,
                    dead_zone=0.0,
                )
            )
            > TRIGGER_ACTIVE_THRESHOLD
        )
        _keyboard_signal = (
            radius_toggle_pressed := self._is_key_down(pygame.K_r)
            and not self.key_pressed_last_frame.get(pygame.K_r, False)
        )
        _gamepad_signal = trigger_right_active and not self._trigger_right_prev_active
        if _keyboard_signal or _gamepad_signal:
            self.BASE_RADIUS = (
                self._LO_BASE if self.BASE_RADIUS == self._HI_BASE else self._HI_BASE
            )
        self.key_pressed_last_frame[pygame.K_r] = radius_toggle_pressed
        self._trigger_right_prev_active = trigger_right_active

        # "inflate/deflate" sphere on hold/release
        try:
            trigger_left_active = (
                _trigger_pressure(
                    self._axis_value(
                        GamepadAxis.TRIGGER_LEFT,
                        dead_zone=0.0,
                    )
                )
                > TRIGGER_ACTIVE_THRESHOLD
            )
            if (
                self._is_key_down(pygame.K_SPACE)
                or trigger_left_active
                or self._button_held(GamepadButton.SOUTH)
            ):
                target = self.BASE_RADIUS + 0.2
                self.active_radius = lerp(
                    self.active_radius,
                    target,
                    self.delta_real_time * self.INFLATE_SPEED,
                )
            else:
                target = self.BASE_RADIUS
                try:
                    lerp_weight = 1.0 - math.exp(
                        -self.INFLATE_SPEED * self.delta_real_time
                    )
                    self.active_radius = lerp(
                        self.active_radius,
                        target,
                        lerp_weight,
                    )
                except Exception:
                    logger.warning("Could not update active radius", exc_info=True)

        except Exception as e:
            # TODO: Very occasionally this raises an exception for some reason, no idea why
            self.active_radius = self.BASE_RADIUS
            logger.exception("Failed to update active radius: %s", e)

        # rotations
        if self._is_key_down(pygame.K_q):
            rz = self.make_rot(0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])
        if self._is_key_down(pygame.K_e):
            rz = self.make_rot(-0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])
        if self._button_held(GamepadButton.ZL):
            rz = self.make_rot(0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])
        if self._button_held(GamepadButton.ZR):
            rz = self.make_rot(-0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])

        right_x = self._axis_value(GamepadAxis.RIGHT_X, dead_zone=0.1)
        right_y = self._axis_value(GamepadAxis.RIGHT_Y, dead_zone=0.1)
        if right_x != 0.0 or right_y != 0.0:
            fps_scale_factor = (self.clock.get_time() / 1000.0) / (1 / self.max_fps)
            stick_scale_factor = 8
            rx = self.make_rot(
                right_x * stick_scale_factor * fps_scale_factor * self.look_speed,
                1,
            )
            ry = self.make_rot(
                right_y * stick_scale_factor * fps_scale_factor * self.look_speed,
                0,
            )
            self.mat[:3, :3] = np.dot(ry, np.dot(rx, self.mat[:3, :3]))
            self.mat[:3, :3] = self.reorthogonalize(self.mat[:3, :3])

        # speed
        if self._is_key_down(pygame.K_j) or self._button_held(GamepadButton.PLUS):
            self.max_velocity += 0.03
        if self._is_key_down(pygame.K_k) or self._button_held(GamepadButton.MINUS):
            self.max_velocity = max(self.max_velocity - 0.03, 0)

        try:
            self._process_mouse()
        except Exception:
            # todo: tbh i'm just not sure if this will error if there's no mouse
            #  device detected (e.g. on pi) so just catching in case
            pass

    def _is_key_down(self, key: int) -> bool:
        return key in self._keyboard_snapshot.pressed_keys

    def _refresh_gamepad_snapshot(self, peripheral_manager: PeripheralManager) -> None:
        self._gamepad_snapshots = peripheral_manager.input_io.gamepad.sample(
            source="renderer.three_fractal",
        )

    def _set_keyboard_snapshot(self, snapshot: KeyboardSnapshot) -> None:
        self._keyboard_snapshot = snapshot

    def _refresh_keyboard_snapshot(self, peripheral_manager: PeripheralManager) -> None:
        try:
            self._keyboard_snapshot = peripheral_manager.input_io.keyboard.sample()
        except (AttributeError, pygame.error):
            return

    def _has_manual_input(self) -> bool:
        if self._keyboard_snapshot.pressed_keys:
            return True
        if self._dpad_value() != GamepadDpadValue():
            return True
        return any(
            self._axis_value(axis, dead_zone=0.1) != 0.0
            for axis in (
                GamepadAxis.LEFT_X,
                GamepadAxis.LEFT_Y,
                GamepadAxis.RIGHT_X,
                GamepadAxis.RIGHT_Y,
            )
        ) or any(
            any(event.snapshot.buttons.values()) for event in self._gamepad_snapshots
        )

    def _button_held(self, button: GamepadButton) -> bool:
        return any(
            event.snapshot.button_held(button) for event in self._gamepad_snapshots
        )

    def _button_tapped(self, button: GamepadButton) -> bool:
        return any(
            event.snapshot.button_tapped(button) for event in self._gamepad_snapshots
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

    def _dpad_value(self) -> GamepadDpadValue:
        return GamepadDpadValue(
            x=max(
                -1,
                min(1, sum(event.snapshot.dpad.x for event in self._gamepad_snapshots)),
            ),
            y=max(
                -1,
                min(1, sum(event.snapshot.dpad.y for event in self._gamepad_snapshots)),
            ),
        )

    def _reset_camera_pos(self):
        # self.mat[3, :3] = np.array([0., 0., 0.])
        # self.mat[:3, :3] = np.array([0., 0., 0.])
        start_pos = [0, 0, 12.0]
        self.mat = np.identity(4, np.float32)
        self.mat[3, :3] = np.array(start_pos)
        self.vel = np.array([0, 0, -self.max_velocity], dtype=np.float32)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        peripheral_manager = self.state.peripheral_manager
        self._refresh_keyboard_snapshot(peripheral_manager)
        self._refresh_gamepad_snapshot(peripheral_manager)
        # Update the target surface if it changed
        if window is not self.target_surface:
            self.target_surface = window

        now = time.monotonic()
        self.delta_real_time = now - (self.last_frame_time or 0.0)
        self.last_frame_time = now

        if self.mode == "auto" and self._check_break_auto(peripheral_manager):
            self._process_input(peripheral_manager)
            self._check_enter_auto(peripheral_manager)
        elif self.mode == "auto":
            self._process_auto()
        else:
            self._process_input(peripheral_manager)
            self._check_enter_auto(peripheral_manager)

        self.mat[3, :3] += self.vel * (self.clock.get_time() / 1000)

        if self.check_collision():
            self._reset_camera_pos()
            # self.mat[3, :3] = np.array([0., 0., 0.])
            # self.mat[:3, :3] = np.array([0., 0., 0.])
            # self.vel = np.array([0, 0, -self.max_velocity], dtype=np.float32)

        # Save previous matrix for motion effects
        self.prevMat = np.copy(self.mat)

        # Render either in normal or tiled mode
        if self.tiled_mode:
            # Set viewport to the small render size
            glViewport(0, 0, self.render_size[0], self.render_size[1])

            # Clear and render
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Render the fractal
            self.render_fractal()

            # Read the pixels from the framebuffer
            glReadPixels(
                0,
                0,
                self.render_size[0],
                self.render_size[1],
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                self.pixels,
            )

            # Upload the pixels to our display texture
            glBindTexture(GL_TEXTURE_2D, self.display_texture)
            glTexSubImage2D(
                GL_TEXTURE_2D,
                0,
                0,
                0,
                self.render_size[0],
                self.render_size[1],
                GL_RGBA,
                GL_UNSIGNED_BYTE,
                self.pixels,
            )

            # Render the tiled view
            self.render_tiled()

            # Transfer to Pygame surface
            self.render_to_surface()
        else:
            # === NORMAL MODE ===
            # Clear the screen
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Render the fractal directly
            self.render_fractal()

            # Transfer to Pygame surface
            self.render_to_surface()

    def check_collision(self):
        # copy origin
        p = np.copy(self.mat[3])

        r = self.active_radius

        # sphere center
        c = np.array([1.0, 1.0, 1.0], dtype=np.float32)

        # start at infinite distance
        d = 1e20

        # hardcode fold used during compilation
        m = 2.0

        # translate point relative to origin
        p[:3] = abs((p[:3] - m / 2) % m - m / 2)

        # calculate distance to sphere (post translation)
        dsphere = (np.linalg.norm(p[:3] - c) - r) / p[3]
        return min(d, dsphere) * 10.0 < 0

    def reset(self):
        try:
            pygame.mouse.set_visible(True)
        except pygame.error:
            logger.debug(
                "Skipping fractal mouse reset; pygame video is not initialized"
            )
        self._delete_gl_texture(getattr(self, "display_texture", None))
        self.initialized = False
        self._auto_started = False
        self.mode = "auto"
        self.shader_runtime.reset()
        self.program = None
        self.mat = None
        self.prevMat = None
        self.display_texture = None
        self.pixels = None
        self.target_surface = None
        self.clock = None
        self.window_size = None
        self.real_window_size = None
        self.render_size = None
        self.screen_center = None
        self.prev_mouse_pos = None
        self.mouse_pos = None
        self.last_frame_time = None
        self.last_update_time = None
        self.delta_real_time = None
        self.surface_array = None
        self.time_initialized = None
        self._trigger_right_prev_active = False
        self._gamepad_snapshots = ()

    @staticmethod
    def _tile_render_size(
        window_size: tuple[int, int],
        orientation: Orientation,
    ) -> tuple[int, int]:
        layout = orientation.layout
        return (
            max(1, window_size[0] // layout.columns),
            max(1, window_size[1] // layout.rows),
        )

    @staticmethod
    def _should_tile(orientation: Orientation) -> bool:
        layout = orientation.layout
        return layout.columns > 1 or layout.rows > 1

    @staticmethod
    def _delete_gl_texture(texture_id: int | None) -> None:
        if texture_id is None:
            return
        try:
            glDeleteTextures([texture_id])
        except GLError:
            logger.debug(
                "Skipping fractal texture delete; OpenGL context is unavailable"
            )


def _trigger_pressure(raw_value: float) -> float:
    if raw_value < 0.0:
        return max(0.0, min(1.0, (raw_value + 1.0) * 0.5))
    return max(0.0, min(1.0, raw_value))


class FractalScene(StatefulBaseRenderer[FractalSceneState]):
    def __init__(self, provider: FractalSceneProvider) -> None:
        self.provider = provider
        self._initial_state: FractalSceneState | None = None
        super().__init__(builder=self.provider)
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self._peripheral_manager: PeripheralManager | None = None
        self._runtime_failed = False

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._initial_state = self.provider.initial_state(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        super().initialize(window, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> StreamNode[FractalSceneState]:
        if self._initial_state is None:
            raise ValueError("FractalScene requires an initial state")
        return self.provider.observable(initial_state=self._initial_state)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        assert self._peripheral_manager is not None
        runtime = self.state.runtime
        if self._runtime_failed:
            return
        if not runtime.is_initialized():
            try:
                runtime.initialize(
                    window=window,
                    peripheral_manager=self._peripheral_manager,
                    orientation=orientation,
                )
            except Exception as exc:
                self._runtime_failed = True
                logger.warning(
                    "Disabling FractalScene; OpenGL runtime failed to initialize: %s",
                    exc,
                )
                return
        runtime.real_process(
            window,
            orientation,
        )

    def reset(self) -> None:
        if self._state is not None:
            self.state.runtime.reset()
        self._initial_state = None
        self._peripheral_manager = None
        self._runtime_failed = False
        super().reset()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the three-fractal renderer directly in a local debug window.",
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
    runtime = FractalRuntime(device=device)

    logger.info(
        "Starting standalone three-fractal debug window width=%s height=%s layout=%s fps=%s",
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
        runtime.initialize(
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
            runtime.real_process(window=display, orientation=orientation)
            pygame.display.flip()
            if display.clock is None:
                raise RuntimeError(
                    "Standalone fractal debug loop did not initialize a clock"
                )
            display.clock.tick(args.fps)
            peripheral_runtime.tick()
        runtime.reset()
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()

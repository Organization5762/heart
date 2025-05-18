import cProfile
import math
import os
import time
from collections import defaultdict

import numpy as np
import pygame
from OpenGL.GL import *
from pygame import OPENGL, DOUBLEBUF
from pygame.math import lerp

from heart import DeviceDisplayMode
from heart.device import Rectangle, Cube, Orientation
from heart.device.local import LocalScreen
from heart.display.renderers import BaseRenderer
from heart.display.shaders.shader import Shader
from heart.display.shaders.util import _UNIFORMS, get_global, set_global_float
from heart.peripheral.core.manager import PeripheralManager


class FractalScene(BaseRenderer):
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

        self.matID = None
        self.prevMatID = None
        self.resID = None
        self.ipdID = None
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

        self.shader: Shader | None = None

        self.last_frame_time = None
        self.delta_real_time = None
        self.virtual_time = 0
        self.INFLATE_SPEED = 10
        self.look_speed = 0.003
        self.key_pressed_last_frame = defaultdict(lambda: False)
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

    def _init_uniforms(self):
        set_global_float(self.sphere_radius_var)

    def _render(self):
        # Create and compile shader
        self._init_uniforms()

        self.shader = Shader()
        self.program = self.shader.create()
        print("Compiled shader!")

        # Get uniform locations
        self.matID = glGetUniformLocation(self.program, "iMat")
        self.prevMatID = glGetUniformLocation(self.program, "iPrevMat")
        self.resID = glGetUniformLocation(self.program, "iResolution")
        self.ipdID = glGetUniformLocation(self.program, "iIPD")

        # Set uniforms
        glUseProgram(self.program)
        glUniform2fv(self.resID, 1, self.window_size)
        glUniform1f(self.ipdID, 0.04)

        # Create and bind fullscreen quad
        fullscreen_quad = np.array([
            -1.0, -1.0, 0.0,
            1.0, -1.0, 0.0,
            -1.0, 1.0, 0.0,
            1.0, 1.0, 0.0],
            dtype=np.float32)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 0, fullscreen_quad)
        glEnableVertexAttribArray(0)

    # Modify initialize to support both modes
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
   ):
        """Initialize the fractal renderer with the given window size"""
        print(f"OpenGL Version: {glGetString(GL_VERSION).decode('utf-8')}")
        print(f"OpenGL Vendor: {glGetString(GL_VENDOR).decode('utf-8')}")
        print(f"OpenGL Renderer: {glGetString(GL_RENDERER).decode('utf-8')}")
        print(f"OpenGL Shading Language Version: {glGetString(GL_SHADING_LANGUAGE_VERSION).decode('utf-8')}")

        if not self.device:
            window_size = (
                1280, 720
            )
        else:
            window_size = (
                self.device.scaled_screen.get_size()
                if isinstance(self.device, LocalScreen)
                else self.device.full_display_size()
            )
        # window_size = window.get_size()
        tiled_mode = isinstance(orientation, Cube)

        self.initialized = True
        self.tiled_mode = tiled_mode
        self.clock = clock
        self.mode = "auto"

        # window_size = window.get_size()

        if self.tiled_mode:
            self.render_size = (window_size[1], window_size[1])
            self.window_size = self.render_size
            self.real_window_size = window_size

            # Create resources for tiled rendering
            self.setup_tiled_rendering()
        else:
            # For normal mode, use the actual window size
            self.window_size = window_size

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
        self.last_update_time = time.time()

        self.shader.set(self.sphere_radius_var, self.BASE_RADIUS)
        self.last_frame_time = time.time()

        self.mode = "auto"

    def setup_tiled_rendering(self):
        """Set up resources for tiled rendering"""
        # Create a pixel buffer to store the rendered result
        self.pixels = np.zeros((self.render_size[0], self.render_size[1], 4), dtype=np.uint8)

        # Create a texture to hold the rendered result for display
        self.display_texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.display_texture)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     self.render_size[0], self.render_size[1],
                     0, GL_RGBA, GL_UNSIGNED_BYTE, None)

    def _apply_pending_uniforms(self):
        """Apply any pending uniform changes to the active shader program"""
        for key, val in self.shader.pending_uniforms.items():
            if key in _UNIFORMS:
                val = _UNIFORMS[key]
                # if type(val) is float and type(cur_val) is not float:
                #     val = to_vec3(val)
            _UNIFORMS[key] = val
            if key in self.shader.keys:
                key_id = self.shader.keys[key]
                try:
                    if type(val) is float:
                        glUniform1f(key_id, val)
                    else:
                        glUniform3fv(key_id, 1, val)
                except Exception as e:
                    print(f"Error setting uniform {key}: {e}")

            # Clear pending uniforms after applying
            self.shader.pending_uniforms = {}

    def render_fractal(self):
        """Render the fractal scene"""
        glUseProgram(self.program)

        # Apply any pending uniforms
        self._apply_pending_uniforms()

        # Set camera matrix uniform
        glUniformMatrix4fv(self.matID, 1, False, self.mat)
        glUniformMatrix4fv(self.prevMatID, 1, False, self.prevMat)

        # Draw
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def render_tiled(self):
        """Render the texture tiled across the screen"""
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
        tiles_x = self.real_window_size[0] // tile_width

        # Clear the screen for the tiled display
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        for i in range(tiles_x):
            x = i * tile_width

            glBegin(GL_QUADS)
            glTexCoord2f(0, 0)
            glVertex2f(x, 0)

            glTexCoord2f(1, 0)
            glVertex2f(x + tile_width, 0)

            glTexCoord2f(1, 1)
            glVertex2f(x + tile_width, tile_height)

            glTexCoord2f(0, 1)
            glVertex2f(x, tile_height)
            self._apply_pending_uniforms()
            glEnd()

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
            return np.array([[1, 0, 0],
                             [0, c, -s],
                             [0, s, c]], dtype=np.float32)
        elif axis_ix == 1:
            return np.array([[c, 0, s],
                             [0, 1, 0],
                             [-s, 0, c]], dtype=np.float32)
        elif axis_ix == 2:
            return np.array([[c, -s, 0],
                             [s, c, 0],
                             [0, 0, 1]], dtype=np.float32)

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

        # pulse spheres
        # pulse = math.sin(2 * math.pi * self.virtual_time)
        # self.active_radius = self.BASE_RADIUS + self.AMPLITUDE * pulse

    def _check_enter_auto(self):
        keys  = pygame.key.get_pressed()
        if keys[pygame.K_LEFTBRACKET]:
            self.reset()
            self.mode = "auto"

    def _check_break_auto(self):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_RIGHTBRACKET]:
            self.mode = "free"

    def _process_input(self, peripheral_manager):
        self._process_keyboard_input(peripheral_manager)

    def _process_keyboard_input(self, peripheral_manager):
        keys = pygame.key.get_pressed()

        # Calculate acceleration based on key input
        acc = np.zeros((3,), dtype=np.float32)
        if keys[pygame.K_a]:
            acc[0] -= self.speed_accel / self.max_fps
        if keys[pygame.K_d]:
            acc[0] += self.speed_accel / self.max_fps
        if keys[pygame.K_w]:
            acc[2] -= self.speed_accel / self.max_fps
        if keys[pygame.K_s]:
            acc[2] += self.speed_accel / self.max_fps


        # Apply acceleration or deceleration
        if np.dot(acc, acc) == 0.0:
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

        # else:
        #     self.vel += np.dot(self.mat[:3, :3].T, acc)
        #     vel_ratio = min(self.max_velocity, 1e20) / (np.linalg.norm(self.vel) + 1e-12)
        #     if vel_ratio < 1.0:
        #         self.vel *= vel_ratio

        # invert the radius
        if keys[pygame.K_r] and not self.key_pressed_last_frame[pygame.K_r]:
            self.BASE_RADIUS = (
                self._LO_BASE if self.BASE_RADIUS == self._HI_BASE
                else self._HI_BASE
            )
        self.key_pressed_last_frame[pygame.K_r] = keys[pygame.K_r]

        # "inflate/deflate" sphere on hold/release
        try:
            if keys[pygame.K_SPACE]:
                target = self.BASE_RADIUS + 0.2
                self.active_radius = lerp(
                    self.active_radius, target, self.delta_real_time * self.INFLATE_SPEED
                )
            else:
                target = self.BASE_RADIUS
                self.active_radius = lerp(
                    self.active_radius, target, self.delta_real_time * self.INFLATE_SPEED
                )
        except Exception as e:
            # TODO: Very occasionally this raises an exception for some reason, no idea why
            self.active_radius = self.BASE_RADIUS
            print(f"error but why: {e}")

        if not self.tiled_mode:
            # eagerly apply the uniforms
            self.shader.set('s_radius', self.active_radius)

        # rotations
        if keys[pygame.K_q]:
            rz = self.make_rot(0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])
        if keys[pygame.K_e]:
            rz = self.make_rot(-0.01, 2)
            self.mat[:3, :3] = np.dot(rz, self.mat[:3, :3])

        # speed
        if keys[pygame.K_j]:
            self.max_velocity += 0.03
        if keys[pygame.K_k]:
            self.max_velocity = max(self.max_velocity - 0.03, 0)

        try:
            self._process_mouse()
        except:
            # todo: tbh i'm just not sure if this will error if there's no mouse
            #  device detected (e.g. on pi) so just catching in case
            pass

    def process(self, window, clock, peripheral_manager, orientation):
        now = time.time()
        self.delta_real_time = now - (self.last_frame_time or 0.0)
        self.last_frame_time = now

        if self.mode == "auto":
            self._process_auto()
            self._check_break_auto()
        else:
            self._process_input(peripheral_manager)
            self._check_enter_auto()


        self.mat[3, :3] += self.vel * (clock.get_time() / 1000)

        if self.check_collision():
            self.mat[3, :3] = np.array([0., 0., 0.])
            self.mat[:3, :3] = np.array([0., 0., 0.])
            self.vel = np.array([0, 0, -self.max_velocity], dtype=np.float32)

        # Save previous matrix for motion effects
        self.prevMat = np.copy(self.mat)

        # Render either in normal or tiled mode
        if self.tiled_mode:
            # queue uniforms to send to shader
            self.shader.set('s_radius', self.active_radius, lazy=True)

            # Set viewport to the small render size
            glViewport(0, 0, self.render_size[0], self.render_size[1])

            # Clear and render
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Render the fractal
            self.render_fractal()

            # Read the pixels from the framebuffer
            glReadPixels(0, 0, self.render_size[0], self.render_size[1], GL_RGBA, GL_UNSIGNED_BYTE, self.pixels)

            # Upload the pixels to our display texture
            glBindTexture(GL_TEXTURE_2D, self.display_texture)
            glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, self.render_size[0], self.render_size[1], GL_RGBA, GL_UNSIGNED_BYTE,
                            self.pixels)

            # Render the tiled view
            self.render_tiled()
        else:
            # === NORMAL MODE ===
            # Clear the screen
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # Render the fractal directly
            self.render_fractal()

        # print fps every second
        if time.time() - self.last_fps_print > 1:
            print(f"fps: {self.clock.get_fps()}")
            self.last_fps_print = time.time()

    def check_collision(self):
        # copy origin
        p = np.copy(self.mat[3])

        # get radius uniform val
        r = get_global(self.sphere_radius_var)

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
        self.initialized = False
        self.mode = "auto"


def main():
    import pygame

    profiling = os.environ.get("PROFILING", "False").lower() == "true"
    check_frames = int(os.environ.get("CHECK_FRAMES", "100"))

    # Initialize pygame
    pygame.init()

    # Set up the display
    WIDTH, HEIGHT = 1280, 720
    screen = pygame.display.set_mode((WIDTH, HEIGHT), OPENGL | DOUBLEBUF)
    # window = pygame.display.set_mode(win_size, OPENGL | DOUBLEBUF)
    pygame.display.set_caption("Mandelbrot Explorer")

    scene = FractalScene(None)

    # Main game loop
    running = True
    clock = pygame.time.Clock()
    if profiling:
        profiler = cProfile.Profile()
        profile_filename = "mandelbrot_profile.prof"
        profiler.enable()

    frame_count = 0

    manager = PeripheralManager()
    manager.detect()
    manager.start()
    try:
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Fill the screen with black
            # screen.fill((0, 0, 0))

            # Process and render
            scene._internal_process(
                screen, clock, manager, Rectangle.with_layout(
                1, 1,
                )
            )

            # Update the display
            pygame.display.flip()
            frame_count += 1

            if profiling and (frame_count >= check_frames):
                profiler.disable()
                profiler.dump_stats(profile_filename)
                break

            clock.tick(60)
    except Exception as e:
        print("exception", e)
    # finally:
    #     if profiling:
    #         # === Profiling Teardown and Analysis ===
    #         profiler.disable()  # Stop profiling
    #         print(f"Profiling finished after {frame_count} frames.")
    #
    #         # --- Option 1: Print stats to console ---
    #         s = io.StringIO()
    #         # Sort by cumulative time spent in function and its callees
    #         ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
    #         ps.print_stats(30)  # Print top 30 lines
    #         print("\n--- Profiling Stats (Sorted by Cumulative Time) ---")
    #         print(s.getvalue())
    #
    #         # You might also want to sort by 'tottime' (total time spent ONLY in the function itself)
    #         s = io.StringIO()
    #         ps = pstats.Stats(profiler, stream=s).sort_stats("tottime")
    #         ps.print_stats(30)  # Print top 30 lines
    #         print("\n--- Profiling Stats (Sorted by Total Time) ---")
    #         print(s.getvalue())
    #
    #         # --- Option 2: Save stats to a file for later analysis ---
    #         profiler.dump_stats(profile_filename)
    #         print(f"\nProfiling data saved to {profile_filename}")
    #         print(
    #             "You can analyze this file later, e.g., using 'snakeviz {profile_filename}'"
    #         )

    print("quitting")
    raise Exception("quitting")

    # why tf does it exit so slow if trying to actually quit gracefully lol
    # pygame.display.quit()
    # pygame.quit()
    # sys.exit()


if __name__ == "__main__":
    main()

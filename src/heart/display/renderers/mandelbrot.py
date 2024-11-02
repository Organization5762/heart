import time
from collections import deque

import numpy as np
import pygame
from numba import jit, prange

from heart.display.renderers import BaseRenderer
from heart.environment import DeviceDisplayMode
from heart.input.direction import DirectionInput, Direction
from heart.input.switch import SwitchSubscriber


class MandelbrotMode(BaseRenderer):
    def __init__(self):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.dimensions_set = False
        self.width = None
        self.height = None
        self.max_iter = 500
        self.max_zoom = 143317203096477.16
        self.zoom = 1
        self.zoom_factor = 1.05
        self.flip = False

        interesting_ofsets = [
            (-0.7450010130148861, 0.11899999957892138),
            (-0.7450010040106548, 0.11900000673128418),
        ]
        self.init_offset_x, self.init_offset_y = interesting_ofsets[0]
        self.offset_x = self.init_offset_x
        self.offset_y = self.init_offset_y
        self.invert_colors = True
        self.rotation_angle = 0
        self.mode = "auto"

        self.debounce_delay = 200
        self.last_dpad_update = 0

        self.last_switch_value = None
        self.time_since_last_update = None
        self.last_frame = None
        self.render_times_window = deque(maxlen=25)
        self.frame_count = 0
        pygame.font.init()
        self.font = pygame.font.Font(None, 20)

        self.coloring_mode = "gray"

    def _switch_feed(self):
        current_value = SwitchSubscriber.get().get_rotation_since_last_button_press()
        return current_value

    # def _dpad_feed(self):
    #     pass

    def clamp(self, n, low, high):
        return max(low, min(n, high))

    def handle_dpad(self):
        dpad = DirectionInput.get_active()
        direction = dpad.get_direction()
        pan_amount = 0.05 / self.zoom
        dpad_trigerred = False
        if direction == Direction.ENTER and self.mode == "free":
            self.reset()
            self.mode = "auto"
            # if self.mode == "auto":
            #     self.mode = "free"
            # else:
            #     self.reset()
            #     self.mode = "auto"
        elif direction == Direction.UP:
            dpad_trigerred = True
            # self.zoom_factor = self.clamp(self.zoom_factor + 0.01, 0.82, 1.3)
            self.offset_y -= pan_amount
        elif direction == Direction.UP_LEFT:
            dpad_trigerred = True
            self.offset_x -= pan_amount
            self.offset_y -= pan_amount
        elif direction == Direction.UP_RIGHT:
            dpad_trigerred = True
            self.offset_x += pan_amount
            self.offset_y -= pan_amount
        elif direction == Direction.DOWN_LEFT:
            dpad_trigerred = True
            self.offset_x -= pan_amount
            self.offset_y += pan_amount
        elif direction == Direction.DOWN_RIGHT:
            dpad_trigerred = True
            self.offset_x += pan_amount
            self.offset_y += pan_amount
        elif direction == Direction.DOWN:
            dpad_trigerred = True
            self.offset_y += pan_amount
        elif direction == Direction.LEFT:
            dpad_trigerred = True
            self.offset_x -= pan_amount
        elif direction == Direction.RIGHT:
            dpad_trigerred = True
            self.offset_x += pan_amount
        elif direction == Direction.SPACE:
            dpad_trigerred = True
            if self.zoom < self.max_zoom:
                self.zoom *= 1.1
        elif direction == Direction.CTRL:
            dpad_trigerred = True
            if self.zoom > 1:
                self.zoom /= 1.1
        elif direction == "y":
            self.coloring_mode = "standard"
        elif direction == "u":
            self.coloring_mode = "gray"

        if dpad_trigerred:
            self.mode = "free"

    def handle_switch(self):
        value = self._switch_feed()
        if self.last_switch_value is None:
            self.last_switch_value = value
        delta = value - self.last_switch_value
        self.zoom_factor = self.clamp(self.zoom_factor + 0.01 * delta, 0.82, 1.3)
        self.last_switch_value = value

    def render_zoom_level(self, window: pygame.Surface):
        zoom_text = f"Zoom: {self.zoom:.2f}"
        offset_text = f"Offset: ({self.offset_x}, {self.offset_y})"
        text_surface = self.font.render(zoom_text, True, (255, 0, 0))  # White text
        text_surface2 = self.font.render(offset_text, True, (255, 0, 0))  # White text
        window.blit(text_surface, (10, 10))
        window.blit(text_surface2, (10, 50))

    def reset(self):
        self.zoom = 1
        self.offset_x = self.init_offset_x
        self.offset_y = self.init_offset_y
        self.invert_colors = False
        self.rotation_angle = 0

    def process(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        if not self.dimensions_set:
            self.height = window.get_height()
            self.width = window.get_width()
        self.handle_switch()
        # self.handle_dpad()
        self.render_mandelbrot(window, clock)
        # self.render_zoom_level(window)
        if self.mode == "auto":
            self.update_zoom()

    def update_zoom(self):
        self.zoom *= self.zoom_factor
        if self.zoom >= self.max_zoom:
            self.zoom = 2 ** -5
            self.invert_colors = not self.invert_colors
            # self.update_rotation()
            # self.flip = not self.flip
        elif self.zoom < 2 ** -5:
            self.zoom = 100000000
            self.invert_colors = not self.invert_colors
            # self.flip = not self.flip
            # self.update_rotation()

    def update_rotation(self):
        self.rotation_angle += 90
        if self.rotation_angle >= 360:
            self.rotation_angle = 0

    def gray_coloring(self, iterations, max_iter):
        # Create a mask for points that have escaped
        escaped = iterations < max_iter

        # # Calculate the factor using square root, similar to the reference code
        # factor = np.sqrt(iterations / max_iter)
        # Apply smoothing formula
        # Normalize the iterations
        factor = iterations / max_iter

        # Apply smoothing (you can experiment with different functions here)
        factor = np.sqrt(factor)

        # Apply a smoother color transition (you can experiment with different functions here)
        # factor = np.sin(factor * np.pi * 0.5)  # This creates a smoother transition

        # Scale the factor to 0-255 range for grayscale
        intensity = (factor * 255).astype(np.uint8)

        # Create the color array
        color = np.zeros((iterations.shape[0], iterations.shape[1], 3), dtype=np.uint8)

        # Set the color for non-escaped points (Mandelbrot set)
        color[~escaped] = np.dstack([intensity[~escaped]])
        # color[~escaped] = np.dstack([255 - intensity[~escaped]])

        # Set the grayscale color for escaped points
        color[escaped] = np.dstack([intensity[escaped]])
        # color[escaped] = intensity[escaped]

        return color

    def standard_coloring(self, iterations, max_iter):
        color_surface = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        color_value = iterations * 0.5 if self.invert_colors else 255 - iterations * 0.5
        color_surface[..., 0] = color_value
        color_surface[..., 1] = color_value
        color_surface[..., 2] = color_value
        return color_surface

    def render_mandelbrot(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        re = np.linspace(
            -3.5 / self.zoom + self.offset_x,
            3.5 / self.zoom + self.offset_x,
            self.width,
        )
        im = np.linspace(
            -2.0 / self.zoom + self.offset_y,
            2.0 / self.zoom + self.offset_y,
            self.height,
        )
        re, im = np.meshgrid(re, im)
        converge_time = get_mandelbrot_converge_time(re, im, self.max_iter)
        color_surface = self.standard_coloring(converge_time, self.max_iter)

        surface_array = np.transpose(color_surface, (1, 0, 2))
        if self.flip:
            surface_array = np.flip(surface_array, axis=0)

        pygame.surfarray.blit_array(window, surface_array)


@jit(nopython=True, parallel=True)
def get_mandelbrot_converge_time(re, im, max_iter):
    height, width = re.shape
    result = np.full((height, width), max_iter, dtype=np.int32)

    for i in prange(height):
        for j in range(width):
            c = complex(re[i, j], im[i, j])
            z = 0.0j
            for k in range(max_iter):
                z = z * z + c
                if abs(z) > 2:
                    result[i, j] = k
                    break

    return result

import time
from collections import deque

import numpy as np
import pygame
from numba import jit, prange

from heart.display.renderers import BaseRenderer
from heart.environment import DeviceDisplayMode
from heart.input.switch import SwitchSubscriber


class MandelbrotMode(BaseRenderer):
    def __init__(self, display_width, display_height):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.dimensions_set = False
        self.width = None
        self.height = None
        self.max_iter = 256
        self.zoom = 1
        self.zoom_factor = 1.05
        self.flip = False

        # semi dive into seahorse region
        self.offset_x = -0.745001
        self.offset_y = 0.119
        self.invert_colors = False
        self.rotation_angle = 0

        self.last_switch_value = None
        self.time_since_last_update = None
        self.last_frame = None
        self.render_times_window = deque(maxlen=25)
        self.frame_count = 0

    def _switch_feed(self):
        current_value = SwitchSubscriber.get().get_rotation_since_last_button_press()
        return current_value

    def clamp(self, n, low, high):
        return max(low, min(n, high))

    def handle_switch(self):
        value = self._switch_feed()
        if self.last_switch_value is None:
            self.last_switch_value = value
        delta = value - self.last_switch_value
        self.zoom_factor = self.clamp(self.zoom_factor + 0.01 * delta, 0.82, 1.3)
        self.last_switch_value = value

    def process(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        if not self.dimensions_set:
            self.height = window.get_height()
            self.width = window.get_width()
        self.handle_switch()
        self.render_mandelbrot(window, clock)
        self.update_zoom()

    def update_zoom(self):
        self.zoom *= self.zoom_factor
        if self.zoom > 100000000:
            self.zoom = 2 ** -4
            self.invert_colors = not self.invert_colors
            # self.update_rotation()
            self.flip = not self.flip
        elif self.zoom < 2 ** -4:
            self.zoom = 100000000
            self.invert_colors = not self.invert_colors
            self.flip = not self.flip
            # self.update_rotation()

    def update_rotation(self):
        self.rotation_angle += 90
        if self.rotation_angle >= 360:
            self.rotation_angle = 0


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

        if self.invert_colors:
            color_values = (converge_time * 255 / self.max_iter).astype(np.uint8)
        else:
            color_values = 255 - (converge_time * 255 / self.max_iter).astype(np.uint8)

        color_surface = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        color_surface[..., 0] = color_values * 1  # Set red channel
        color_surface[..., 1] = color_values * 1  # Set green channel
        color_surface[..., 2] = color_values * 1  # Set blue channel

        surface_array = np.transpose(color_surface, (1, 0, 2))
        if self.flip:
            surface_array = np.flip(surface_array, axis=0)

        pygame.surfarray.blit_array(window, surface_array)

        # render_surface = pygame.surfarray.make_surface(np.transpose(color_surface, (1, 0, 2)))

        # Scale the render surface up to the display resolution
        # scaled_surface = pygame.transform.scale(render_surface, (self.render_width, self.render_height))

        # Apply rotation
        # rotated_surface = pygame.transform.rotate(render_surface, self.rotation_angle)

        # Calculate position to center the rotated surface
        # pos_x = (self.render_width - rotated_surface.get_width()) // 2
        # pos_y = (self.render_height - rotated_surface.get_height()) // 2

        # Blit the rotated and scaled surface onto the window
        # window.blit(rotated_surface, (0, 0))


# @jit(nopython=True)
# def mandelbrot(height, width, max_iter, zoom):
#     result = np.zeros((height, width), dtype=np.int64)
#     for y in range(height):
#         for x in range(width):
#             real = 3.5 * x / width - 2.5
#             imag = 2.0 * y / height - 1.0
#             c = real + imag * 1j
#             z = 0j
#             for i in range(max_iter):
#                 if abs(z) > 2:
#                     break
#                 z = z**2 + c
#             result[y, x] = i
#     return result


# def get_mandelbrot_converge_time(re, im, max_iter):
#     c = re + 1j * im
#     z = np.zeros(c.shape, dtype=np.complex128)
#     div_time = np.full(c.shape, max_iter, dtype=int)
#
#     for i in range(max_iter):
#         mask = np.abs(z) <= 2
#         z[mask] = z[mask] ** 2 + c[mask]
#         div_time[mask & (np.abs(z) > 2)] = i
#
#     return div_time


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

import pygame

from heart.display.renderers import BaseRenderer
import numpy as np

from heart.input.switch import SwitchSubscriber


class MandelbrotMode(BaseRenderer):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.max_iter = 256
        self.zoom = 1
        self.zoom_factor = 1.05

        # semi dive into seahorse region
        self.offset_x = -0.745001
        self.offset_y = 0.119
        self.invert_colors = False
        self.rotation_angle = 0

        self.last_switch_value = None

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
        self.zoom_factor = self.clamp(self.zoom_factor + 0.001 * delta, 1.01, 1.1)
        # print(self.zoom_factor)
        self.last_switch_value = value

    def process(self, window, clock):
        self.handle_switch()
        self.render_mandelbrot(window, clock)
        self.update_zoom()

    def update_zoom(self):
        self.zoom *= self.zoom_factor
        if self.zoom > 100000000:
            self.zoom = 2 ** -4
            self.invert_colors = not self.invert_colors
            self.update_rotation()

    def get_mandelbrot_converge_time(self, re, im, max_iter):
        c = re + 1j * im
        z = np.zeros(c.shape, dtype=np.complex128)
        div_time = np.full(c.shape, max_iter, dtype=int)

        for i in range(max_iter):
            mask = np.abs(z) <= 2
            z[mask] = z[mask] ** 2 + c[mask]
            div_time[mask & (np.abs(z) > 2)] = i

        return div_time

    def update_rotation(self):
        self.rotation_angle += 90
        if self.rotation_angle >= 360:
            self.rotation_angle = 0

    def render_mandelbrot(self, window, clock):
        re = np.linspace(-3.5 / self.zoom + self.offset_x, 3.5 / self.zoom + self.offset_x, self.width)
        im = np.linspace(-2.0 / self.zoom + self.offset_y, 2.0 / self.zoom + self.offset_y, self.height)
        re, im = np.meshgrid(re, im)
        converge_time = self.get_mandelbrot_converge_time(re, im, self.max_iter)

        if self.invert_colors:
            color_values = (converge_time * 255 / self.max_iter).astype(np.uint8)
        else:
            color_values = 255 - (converge_time * 255 / self.max_iter).astype(np.uint8)

        color_surface = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        color_surface[..., 0] = color_values  # Set red channel
        color_surface[..., 1] = color_values  # Set red channel
        color_surface[..., 2] = color_values  # Set red channel

        # negative_space_color = (0, 0, 100)  # Example dark gray color
        # mask = converge_time == self.max_iter
        # color_surface[mask] = negative_space_color

        surface = pygame.surfarray.make_surface(
            np.transpose(
                color_surface,
                (1, 0, 2)
            )
        )
        window.blit(surface, (0, 0))
        window.blit(
            pygame.transform.rotate(window, self.rotation_angle), (0, 0)
        )

from __future__ import annotations

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.doppler.provider import DopplerStateProvider
from heart.renderers.doppler.state import DopplerState

DEFAULT_HUE_EXTENT = 2.0 / 3.0


class DopplerRenderer(StatefulBaseRenderer[DopplerState]):
    """Render a Doppler-style 3D particle effect credited to Sri."""

    def __init__(
        self, builder: DopplerStateProvider, hue_extent: float = DEFAULT_HUE_EXTENT
    ):
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.FULL
        self._hue_extent = hue_extent
        self._max_speed = builder.max_speed

    def _project_points(
        self, positions: np.ndarray, screen_size: tuple[int, int]
    ) -> tuple[np.ndarray, np.ndarray]:
        width, height = screen_size
        aspect = width / max(height, 1)
        focal_length = 1.2
        camera_distance = 3.0

        z = camera_distance - positions[:, 2]
        z = np.clip(z, 0.1, None)

        scale = focal_length / z
        x = positions[:, 0] * scale * aspect
        y = positions[:, 1] * scale

        px = (x + 0.5) * width
        py = (y + 0.5) * height
        return px, py

    def _hsv_to_rgb(self, h: np.ndarray, s: np.ndarray, v: np.ndarray) -> np.ndarray:
        h = np.mod(h, 1.0)
        i = np.floor(h * 6).astype(int)
        f = h * 6 - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        r = np.empty_like(h)
        g = np.empty_like(h)
        b = np.empty_like(h)

        idx = i % 6 == 0
        r[idx], g[idx], b[idx] = v[idx], t[idx], p[idx]
        idx = i == 1
        r[idx], g[idx], b[idx] = q[idx], v[idx], p[idx]
        idx = i == 2
        r[idx], g[idx], b[idx] = p[idx], v[idx], t[idx]
        idx = i == 3
        r[idx], g[idx], b[idx] = p[idx], q[idx], v[idx]
        idx = i == 4
        r[idx], g[idx], b[idx] = t[idx], p[idx], v[idx]
        idx = i % 6 == 5
        r[idx], g[idx], b[idx] = v[idx], p[idx], q[idx]

        rgb = np.stack((r, g, b), axis=-1)
        return (np.clip(rgb, 0.0, 1.0) * 255).astype(np.uint8)

    def _compute_colours(self, state: DopplerState, dt: float) -> np.ndarray:
        if dt <= 0:
            dt = 1 / 60
        velocity = state.velocity
        delta_v = velocity - state.previous_velocity
        acceleration = delta_v / dt

        direction = velocity / np.maximum(np.linalg.norm(velocity, axis=1, keepdims=True), 1e-6)
        doppler_component = (-direction[:, 2] + 1.0) * 0.5
        hue = doppler_component * self._hue_extent

        accel_magnitude = np.linalg.norm(acceleration, axis=1)
        brightness = np.clip(accel_magnitude / (self._max_speed * 2.0), 0.0, 1.0)
        saturation = np.clip(
            0.3 + accel_magnitude / (self._max_speed * 3.0), 0.3, 1.0
        )

        return self._hsv_to_rgb(hue, saturation, brightness)

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        dt = max(state.last_dt, 1 / 120)
        colours = self._compute_colours(state, dt)

        window.fill((0, 0, 0))
        width, height = window.get_size()
        px, py = self._project_points(state.position, (width, height))

        valid = (px >= 0) & (px < width) & (py >= 0) & (py < height)

        for index in np.where(valid)[0]:
            pygame.draw.circle(
                window,
                colours[index].tolist(),
                (int(px[index]), int(py[index])),
                2,
            )

"""Doppler-inspired particle renderer credited to Sri.

This renderer simulates a 3D particle field and colours each particle using a
red/blue hue gradient based on the direction of motion relative to the viewer.
Acceleration is derived from per-frame velocity changes so faster-moving and
rapidly-changing particles appear brighter.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class ParticleState:
    """Container holding particle kinematics for a single step."""

    position: np.ndarray
    velocity: np.ndarray
    previous_velocity: np.ndarray


class DopplerRenderer(BaseRenderer):
    """Render a Doppler-style 3D particle effect credited to Sri."""

    def __init__(
        self,
        particle_count: int = 256,
        field_radius: float = 1.0,
        max_speed: float = 1.5,
        hue_extent: float = 2.0 / 3.0,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

        self._particle_count = particle_count
        self._field_radius = field_radius
        self._max_speed = max_speed
        self._hue_extent = hue_extent

        self._state = self._initial_state()

    def _initial_state(self) -> ParticleState:
        position = np.random.uniform(
            low=-self._field_radius,
            high=self._field_radius,
            size=(self._particle_count, 3),
        )
        velocity = np.random.uniform(
            low=-0.5,
            high=0.5,
            size=(self._particle_count, 3),
        )
        return ParticleState(
            position=position.astype(np.float32),
            velocity=velocity.astype(np.float32),
            previous_velocity=velocity.astype(np.float32).copy(),
        )

    def reset(self) -> None:
        self._state = self._initial_state()

    def _random_acceleration(self) -> np.ndarray:
        return np.random.normal(
            loc=0.0, scale=0.75, size=(self._particle_count, 3)
        ).astype(np.float32)

    def _integrate(self, state: ParticleState, dt: float) -> None:
        acceleration = self._random_acceleration()
        state.previous_velocity[:] = state.velocity

        state.velocity += acceleration * dt
        speed = np.linalg.norm(state.velocity, axis=1, keepdims=True)
        mask = speed > self._max_speed
        if np.any(mask):
            scale = (self._max_speed / speed[mask]).reshape(-1, 1)
            state.velocity[mask[:, 0]] *= scale

        state.position += state.velocity * dt

        for axis in range(3):
            over = state.position[:, axis] > self._field_radius
            under = state.position[:, axis] < -self._field_radius
            if np.any(over):
                state.position[over, axis] = self._field_radius
                state.velocity[over, axis] *= -1.0
            if np.any(under):
                state.position[under, axis] = -self._field_radius
                state.velocity[under, axis] *= -1.0

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

    def _compute_colours(self, state: ParticleState, dt: float) -> np.ndarray:
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
        saturation = np.clip(0.3 + accel_magnitude / (self._max_speed * 3.0), 0.3, 1.0)

        return self._hsv_to_rgb(hue, saturation, brightness)

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        dt = max(clock.get_time() / 1000.0, 1 / 120)

        self._integrate(self._state, dt)
        colours = self._compute_colours(self._state, dt)

        window.fill((0, 0, 0))
        width, height = window.get_size()
        px, py = self._project_points(self._state.position, (width, height))

        valid = (
            (px >= 0)
            & (px < width)
            & (py >= 0)
            & (py < height)
        )

        for index in np.where(valid)[0]:
            pygame.draw.circle(
                window,
                colours[index].tolist(),
                (int(px[index]), int(py[index])),
                2,
            )
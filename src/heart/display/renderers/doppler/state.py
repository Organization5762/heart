from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DopplerState:
    position: np.ndarray
    velocity: np.ndarray
    previous_velocity: np.ndarray
    last_dt: float

    @classmethod
    def initial(cls, particle_count: int, field_radius: float) -> "DopplerState":
        position = np.random.uniform(
            low=-field_radius, high=field_radius, size=(particle_count, 3)
        ).astype(np.float32)
        velocity = np.random.uniform(low=-0.5, high=0.5, size=(particle_count, 3)).astype(
            np.float32
        )
        return cls(
            position=position,
            velocity=velocity,
            previous_velocity=velocity.copy(),
            last_dt=1 / 60,
        )

    def advance(
        self, acceleration: np.ndarray, dt: float, max_speed: float, field_radius: float
    ) -> "DopplerState":
        position = self.position.copy()
        velocity = self.velocity.copy()
        previous_velocity = self.velocity.copy()

        velocity += acceleration * dt
        speed = np.linalg.norm(velocity, axis=1, keepdims=True)
        mask = speed > max_speed
        if np.any(mask):
            velocity[mask[:, 0]] *= (max_speed / speed[mask]).reshape(-1, 1)

        position += velocity * dt

        for axis in range(3):
            over = position[:, axis] > field_radius
            under = position[:, axis] < -field_radius
            if np.any(over):
                position[over, axis] = field_radius
                velocity[over, axis] *= -1.0
            if np.any(under):
                position[under, axis] = -field_radius
                velocity[under, axis] *= -1.0

        return DopplerState(
            position=position,
            velocity=velocity,
            previous_velocity=previous_velocity,
            last_dt=dt,
        )

from __future__ import annotations

import numpy as np
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider

from .state import DopplerState


class DopplerStateProvider(ObservableProvider[DopplerState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        particle_count: int = 256,
        field_radius: float = 1.0,
        max_speed: float = 1.5,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._particle_count = particle_count
        self._field_radius = field_radius
        self._max_speed = max_speed

    def _random_acceleration(self) -> np.ndarray:
        return np.random.normal(
            loc=0.0, scale=0.75, size=(self._particle_count, 3)
        ).astype(np.float32)

    def _initial_state(self) -> DopplerState:
        position = np.random.uniform(
            low=-self._field_radius, high=self._field_radius, size=(self._particle_count, 3)
        ).astype(np.float32)
        velocity = np.random.uniform(
            low=-0.5, high=0.5, size=(self._particle_count, 3)
        ).astype(np.float32)
        return DopplerState(
            position=position,
            velocity=velocity,
            previous_velocity=velocity.copy(),
            last_dt=1 / 60,
        )

    def _advance_state(
        self, state: DopplerState, *, acceleration: np.ndarray, dt: float
    ) -> DopplerState:
        position = state.position.copy()
        velocity = state.velocity.copy()
        previous_velocity = state.velocity.copy()

        velocity += acceleration * dt
        speed = np.linalg.norm(velocity, axis=1, keepdims=True)
        mask = speed > self._max_speed
        if np.any(mask):
            velocity[mask[:, 0]] *= (self._max_speed / speed[mask]).reshape(-1, 1)

        position += velocity * dt

        for axis in range(3):
            over = position[:, axis] > self._field_radius
            under = position[:, axis] < -self._field_radius
            if np.any(over):
                position[over, axis] = self._field_radius
                velocity[over, axis] *= -1.0
            if np.any(under):
                position[under, axis] = -self._field_radius
                velocity[under, axis] *= -1.0

        return DopplerState(
            position=position,
            velocity=velocity,
            previous_velocity=previous_velocity,
            last_dt=dt,
        )

    def observable(self) -> reactivex.Observable[DopplerState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = self._initial_state()

        def advance_state(
            state: DopplerState, latest: tuple[object, object]
        ) -> DopplerState:
            clock = latest[1]
            dt_seconds = max(clock.get_time() / 1000.0, 1 / 120)
            acceleration = self._random_acceleration()
            return self._advance_state(
                state,
                acceleration=acceleration,
                dt=dt_seconds,
            )

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

    @property
    def max_speed(self) -> float:
        return self._max_speed

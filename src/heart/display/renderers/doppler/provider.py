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

    def observable(self) -> reactivex.Observable[DopplerState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = DopplerState.initial(
            particle_count=self._particle_count, field_radius=self._field_radius
        )

        def advance_state(
            state: DopplerState, latest: tuple[object, object]
        ) -> DopplerState:
            clock = latest[1]
            dt_seconds = max(clock.get_time() / 1000.0, 1 / 120)
            acceleration = self._random_acceleration()
            return state.advance(
                acceleration=acceleration,
                dt=dt_seconds,
                max_speed=self._max_speed,
                field_radius=self._field_radius,
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

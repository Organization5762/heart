from __future__ import annotations

import pygame
import reactivex
from reactivex import operators as ops
from reactivex.subject import BehaviorSubject

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.flame.state import FlameState
from heart.utilities.reactivex_threads import pipe_in_background


class FlameStateProvider(ObservableProvider[FlameState]):
    def __init__(self) -> None:
        self._initial_time = pygame.time.get_ticks() * 2 / 1000.0
        self._initial_state = FlameState(time_seconds=self._initial_time, dt_seconds=0.0)
        self._latest_state = BehaviorSubject(self._initial_state)

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[FlameState]:
        clocks = pipe_in_background(
            peripheral_manager.clock,
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        def to_state(clock: pygame.time.Clock) -> FlameState:
            return FlameState(
                time_seconds=pygame.time.get_ticks() * 2 / 1000.0,
                dt_seconds=max(clock.get_time() / 1000.0, 1.0 / 120.0),
            )

        return pipe_in_background(
            peripheral_manager.game_tick,
            ops.with_latest_from(clocks),
            ops.map(lambda latest: to_state(clock=latest[1])),
            ops.do_action(self._latest_state.on_next),
            ops.start_with(self._initial_state),
            ops.share(),
        )

    @property
    def latest_state(self) -> FlameState:
        return self._latest_state.value

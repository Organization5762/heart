from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.display.renderers.l_system.state import LSystemState
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider


class LSystemStateProvider(ObservableProvider[LSystemState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        update_interval_ms: float = 1000.0,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._update_interval_ms = update_interval_ms

    def observable(self) -> reactivex.Observable[LSystemState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = LSystemState.initial()

        def advance(state: LSystemState, clock: Clock) -> LSystemState:
            return state.advance(
                dt_ms=float(clock.get_time()),
                update_interval_ms=self._update_interval_ms,
            )

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

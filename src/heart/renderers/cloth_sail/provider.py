from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.cloth_sail.state import ClothSailState
from heart.utilities.reactivex_threads import pipe_in_background


class ClothSailStateProvider(ObservableProvider[ClothSailState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[ClothSailState]:
        clocks = pipe_in_background(
            self._peripheral_manager.clock,

            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = ClothSailState()

        def advance_state(
            state: ClothSailState, clock: Clock
        ) -> ClothSailState:
            dt_seconds = max(clock.get_time() / 1000.0, 1.0 / 120.0)
            return ClothSailState(elapsed_seconds=state.elapsed_seconds + dt_seconds)

        return (
            pipe_in_background(
                self._peripheral_manager.game_tick,
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

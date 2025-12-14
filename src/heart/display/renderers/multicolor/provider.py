from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.display.renderers.multicolor.state import MulticolorState
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider


class MulticolorStateProvider(ObservableProvider[MulticolorState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[MulticolorState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = MulticolorState()

        def advance_state(
            state: MulticolorState, clock: Clock
        ) -> MulticolorState:
            dt_seconds = max(clock.get_time() / 1000.0, 1.0 / 120.0)
            return state.advance(dt_seconds)

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.heart_title_screen.state import HeartTitleScreenState


class HeartTitleScreenStateProvider(ObservableProvider[HeartTitleScreenState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[HeartTitleScreenState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = HeartTitleScreenState()

        def advance_state(
            state: HeartTitleScreenState, clock: Clock
        ) -> HeartTitleScreenState:
            frame_ms = max(clock.get_time(), 0)
            return state.advance(frame_ms)

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

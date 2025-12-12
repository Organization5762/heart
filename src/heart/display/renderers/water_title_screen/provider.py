from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.display.renderers.water_title_screen.state import \
    WaterTitleScreenState
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider


class WaterTitleScreenStateProvider(ObservableProvider[WaterTitleScreenState]):
    def __init__(self, peripheral_manager: PeripheralManager, wave_speed: float = 0.5):
        self._peripheral_manager = peripheral_manager
        self._wave_speed = wave_speed

    def observable(self) -> reactivex.Observable[WaterTitleScreenState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = WaterTitleScreenState.initial()

        def advance_state(state: WaterTitleScreenState, clock: Clock) -> WaterTitleScreenState:
            dt_seconds = max(clock.get_time() / 1000.0, 1.0 / 120.0)
            return state.advance(self._wave_speed, dt_seconds)

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

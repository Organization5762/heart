from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.water_title_screen.state import WaterTitleScreenState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_WAVE_SPEED = 0.5


class WaterTitleScreenStateProvider(ObservableProvider[WaterTitleScreenState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        wave_speed: float = DEFAULT_WAVE_SPEED,
    ):
        self._peripheral_manager = peripheral_manager
        self._wave_speed = wave_speed

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[WaterTitleScreenState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = WaterTitleScreenState()

        def advance_state(
            state: WaterTitleScreenState,
            frame_tick: object,
        ) -> WaterTitleScreenState:
            dt_seconds = max(frame_tick.delta_s, 1.0 / 120.0)
            return WaterTitleScreenState(
                wave_offset=state.wave_offset + self._wave_speed * dt_seconds * 60.0
            )

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

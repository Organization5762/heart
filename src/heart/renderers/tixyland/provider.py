from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.tixyland.state import TixylandState
from heart.utilities.reactivex_threads import pipe_in_background


class TixylandStateProvider(ObservableProvider[TixylandState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[TixylandState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = TixylandState()

        def advance_state(
            state: TixylandState,
            frame_tick: object,
        ) -> TixylandState:
            delta_seconds = max(frame_tick.delta_ms, 0.0) / 1000
            return TixylandState(time_seconds=state.time_seconds + delta_seconds)

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

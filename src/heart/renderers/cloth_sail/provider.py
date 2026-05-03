from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.cloth_sail.state import ClothSailState
from heart.utilities.reactivex_threads import pipe_in_background


class ClothSailStateProvider(ObservableProvider[ClothSailState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[ClothSailState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = ClothSailState()

        def advance_state(
            state: ClothSailState,
            frame_tick: object,
        ) -> ClothSailState:
            dt_seconds = max(frame_tick.delta_s, 1.0 / 120.0)
            return ClothSailState(elapsed_seconds=state.elapsed_seconds + dt_seconds)

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

from __future__ import annotations

import heart.utilities.reactive as reactive
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.porthole_window.state import PortholeWindowState
from heart.utilities.reactive import operators as ops
from heart.utilities.reactive_threads import (pipe_in_background,
                                              start_with_once)


class PortholeWindowStateProvider(ObservableProvider[PortholeWindowState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactive.Observable[PortholeWindowState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = PortholeWindowState()

        def advance_state(
            state: PortholeWindowState,
            frame_tick: object,
        ) -> PortholeWindowState:
            delta_seconds = max(frame_tick.delta_ms, 0.0) / 1000.0
            return PortholeWindowState(
                elapsed_seconds=state.elapsed_seconds + delta_seconds
            )

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance_state, seed=initial_state),
                start_with_once(initial_state),
                ops.share(),
            )
        )

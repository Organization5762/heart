from __future__ import annotations

from manyfold import Subscribable

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.renderers.porthole_window.state import PortholeWindowState


class PortholeWindowStateProvider(StateProvider[PortholeWindowState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def states(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> Subscribable[PortholeWindowState]:
        frame_ticks = self._peripheral_manager.input_io.frame_tick_stream()
        initial_state = PortholeWindowState()

        def advance_state(
            state: PortholeWindowState, frame_tick: object
        ) -> PortholeWindowState:
            delta_seconds = max(frame_tick.delta_ms, 0.0) / 1000.0
            return PortholeWindowState(
                elapsed_seconds=state.elapsed_seconds + delta_seconds
            )

        return frame_ticks.scan(advance_state, seed=initial_state).start_with(
            initial_state
        )

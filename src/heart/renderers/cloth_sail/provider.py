from __future__ import annotations

from manyfold import Subscribable

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.renderers.cloth_sail.state import ClothSailState


class ClothSailStateProvider(StateProvider[ClothSailState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def states(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> Subscribable[ClothSailState]:
        frame_ticks = self._peripheral_manager.input_io.frame_tick_stream()
        initial_state = ClothSailState()

        def advance_state(state: ClothSailState, frame_tick: object) -> ClothSailState:
            dt_seconds = max(frame_tick.delta_s, 1.0 / 120.0)
            return ClothSailState(elapsed_seconds=state.elapsed_seconds + dt_seconds)

        return frame_ticks.scan(advance_state, seed=initial_state).start_with(
            initial_state
        )

from __future__ import annotations

from manyfold import StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.cloth_sail.state import ClothSailState


class ClothSailStateProvider(ObservableProvider[ClothSailState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[ClothSailState]:
        frame_ticks = (
            self._peripheral_manager.frame_tick_controller.observable()
        )
        initial_state = ClothSailState()

        def advance_state(state: ClothSailState, frame_tick: object) -> ClothSailState:
            dt_seconds = max(frame_tick.delta_s, 1.0 / 120.0)
            return ClothSailState(elapsed_seconds=state.elapsed_seconds + dt_seconds)

        return (
            frame_ticks.scan(advance_state, seed=initial_state)
            .start_with(initial_state)


        )

from __future__ import annotations

from manyfold import StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.tixyland.state import TixylandState


class TixylandStateProvider(ObservableProvider[TixylandState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[TixylandState]:
        frame_ticks = (
            self._peripheral_manager.input_io.frame_tick_stream()
        )
        initial_state = TixylandState()

        def advance_state(state: TixylandState, frame_tick: object) -> TixylandState:
            delta_seconds = max(frame_tick.delta_ms, 0.0) / 1000
            return TixylandState(time_seconds=state.time_seconds + delta_seconds)

        return (
            frame_ticks.scan(advance_state, seed=initial_state)
            .start_with(initial_state)


        )

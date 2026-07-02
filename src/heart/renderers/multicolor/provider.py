from __future__ import annotations

from manyfold import StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.multicolor.state import MulticolorState


class MulticolorStateProvider(ObservableProvider[MulticolorState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[MulticolorState]:
        frame_ticks = self._peripheral_manager.input_io.frame_tick_stream()
        initial_state = MulticolorState()

        def advance_state(
            state: MulticolorState, frame_tick: object
        ) -> MulticolorState:
            dt_seconds = max(frame_tick.delta_s, 1.0 / 120.0)
            return MulticolorState(elapsed_seconds=state.elapsed_seconds + dt_seconds)

        return frame_ticks.scan(advance_state, seed=initial_state).start_with(
            initial_state
        )

from __future__ import annotations

from manyfold import StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.heart_title_screen.state import HeartTitleScreenState

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400


class HeartTitleScreenStateProvider(ObservableProvider[HeartTitleScreenState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[HeartTitleScreenState]:
        frame_ticks = self._peripheral_manager.input_io.frame_tick_stream()
        initial_state = HeartTitleScreenState()

        def advance_state(
            state: HeartTitleScreenState, frame_tick: object
        ) -> HeartTitleScreenState:
            return self._advance_state(state=state, frame_ms=frame_tick.delta_ms)

        return frame_ticks.scan(advance_state, seed=initial_state).start_with(
            initial_state
        )

    def _advance_state(
        self, *, state: HeartTitleScreenState, frame_ms: float
    ) -> HeartTitleScreenState:
        safe_frame_ms = max(frame_ms, 0.0)
        elapsed_ms = state.elapsed_ms + safe_frame_ms
        heart_up = state.heart_up
        if elapsed_ms > DEFAULT_TIME_BETWEEN_FRAMES_MS:
            elapsed_ms = 0.0
            heart_up = not heart_up
        return HeartTitleScreenState(heart_up=heart_up, elapsed_ms=elapsed_ms)

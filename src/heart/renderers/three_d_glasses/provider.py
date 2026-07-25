from __future__ import annotations

from manyfold import Subscribable
from manyfold.architecture import PubSubObservable

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.renderers.three_d_glasses.state import ThreeDGlassesState

DEFAULT_FRAME_DURATION_MS = 650
DEFAULT_FRAME_COUNT = 0


class ThreeDGlassesStateProvider(StateProvider[ThreeDGlassesState]):
    def __init__(
        self,
        frame_duration_ms: int = DEFAULT_FRAME_DURATION_MS,
        frame_count: int = DEFAULT_FRAME_COUNT,
    ) -> None:
        if frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        self._frame_duration_ms = frame_duration_ms
        self._frame_count = frame_count

    def initial_state(self) -> ThreeDGlassesState:
        return ThreeDGlassesState()

    def set_frame_count(self, frame_count: int) -> None:
        self._frame_count = max(frame_count, 0)

    def next_state(
        self, state: ThreeDGlassesState, *, elapsed_ms: float
    ) -> ThreeDGlassesState:
        if self._frame_count == 0:
            return state
        total_elapsed = state.elapsed_ms + elapsed_ms
        index = state.current_index
        if total_elapsed >= self._frame_duration_ms:
            total_elapsed %= self._frame_duration_ms
            index = (index + 1) % self._frame_count
        return ThreeDGlassesState(current_index=index, elapsed_ms=total_elapsed)

    def states(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: ThreeDGlassesState,
    ) -> Subscribable[ThreeDGlassesState]:
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        tick_updates = frame_ticks.map(
            lambda frame_tick: (
                lambda state: self.next_state(
                    state, elapsed_ms=float(frame_tick.delta_ms)
                )
            )
        )
        return PubSubObservable.merge(tick_updates).state(
            initial_state,
            lambda state, update: update(state),
        )

from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.three_d_glasses.state import ThreeDGlassesState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_FRAME_DURATION_MS = 650
DEFAULT_FRAME_COUNT = 0


class ThreeDGlassesStateProvider(ObservableProvider[ThreeDGlassesState]):
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

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: ThreeDGlassesState,
    ) -> reactivex.Observable[ThreeDGlassesState]:
        frame_ticks = pipe_in_background(
            peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        tick_updates = pipe_in_background(
            frame_ticks,
            ops.map(
                lambda frame_tick: lambda state: self.next_state(
                    state,
                    elapsed_ms=float(frame_tick.delta_ms),
                )
            ),
        )

        return pipe_in_background(
            tick_updates,
            ops.scan(lambda state, update: update(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

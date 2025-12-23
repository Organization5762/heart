from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.three_d_glasses.state import ThreeDGlassesState


class ThreeDGlassesStateProvider(ObservableProvider[ThreeDGlassesState]):
    def __init__(self, frame_duration_ms: int = 650) -> None:
        if frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be positive")
        self._frame_duration_ms = frame_duration_ms

    def initial_state(self) -> ThreeDGlassesState:
        return ThreeDGlassesState()

    def next_state(
        self, state: ThreeDGlassesState, *, frame_count: int, elapsed_ms: float
    ) -> ThreeDGlassesState:
        if frame_count == 0:
            return state

        total_elapsed = state.elapsed_ms + elapsed_ms
        index = state.current_index

        if total_elapsed >= self._frame_duration_ms:
            total_elapsed %= self._frame_duration_ms
            index = (index + 1) % frame_count

        return ThreeDGlassesState(current_index=index, elapsed_ms=total_elapsed)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        frame_count: int,
        initial_state: ThreeDGlassesState,
    ) -> reactivex.Observable[ThreeDGlassesState]:
        clocks = peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        tick_updates = peripheral_manager.game_tick.pipe(
            ops.filter(lambda tick: tick is not None),
            ops.with_latest_from(clocks),
            ops.map(
                lambda latest: lambda state: self.next_state(
                    state,
                    frame_count=frame_count,
                    elapsed_ms=float(latest[1].get_time()),
                )
            ),
        )

        return tick_updates.pipe(
            ops.scan(lambda state, update: update(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

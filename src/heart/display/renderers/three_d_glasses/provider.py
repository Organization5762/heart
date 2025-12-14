from __future__ import annotations

from heart.display.renderers.three_d_glasses.state import ThreeDGlassesState


class ThreeDGlassesStateProvider:
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

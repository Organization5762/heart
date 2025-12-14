import reactivex
from reactivex.subject import BehaviorSubject

from heart.display.renderers.three_d_glasses.state import ThreeDGlassesState
from heart.peripheral.core.providers import ObservableProvider


class ThreeDGlassesStateProvider(ObservableProvider[ThreeDGlassesState]):
    def __init__(self, frame_count: int, frame_duration_ms: int = 650) -> None:
        if frame_count <= 0:
            raise ValueError("ThreeDGlassesStateProvider requires at least one frame")

        self._frame_count = frame_count
        self._frame_duration_ms = frame_duration_ms
        self._state = BehaviorSubject(ThreeDGlassesState(current_index=0, elapsed_ms=0.0))

    def observable(self) -> reactivex.Observable[ThreeDGlassesState]:
        return self._state

    def advance(self, elapsed_ms: float) -> None:
        previous = self._state.value
        accumulated = previous.elapsed_ms + elapsed_ms
        frame_steps = int(accumulated // self._frame_duration_ms)
        next_index = (previous.current_index + frame_steps) % self._frame_count
        next_elapsed = accumulated % self._frame_duration_ms
        self._state.on_next(
            ThreeDGlassesState(current_index=next_index, elapsed_ms=next_elapsed)
        )

    @property
    def initial_state(self) -> ThreeDGlassesState:
        return self._state.value

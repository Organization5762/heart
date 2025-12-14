import time

import reactivex
from reactivex import operators as ops

from heart.display.renderers.cloth_sail.state import ClothSailState
from heart.peripheral.core.providers import ObservableProvider


class ClothSailStateProvider(ObservableProvider[ClothSailState]):
    def __init__(self, tick_seconds: float = 1 / 60) -> None:
        self._start_time = time.perf_counter()
        self._tick_seconds = tick_seconds
        self._initial_state = ClothSailState(start_time=self._start_time, elapsed=0.0)

    def observable(self) -> reactivex.Observable[ClothSailState]:
        def tick_to_state(_: int, __: ClothSailState | None = None) -> ClothSailState:
            elapsed = time.perf_counter() - self._start_time
            return ClothSailState(start_time=self._start_time, elapsed=elapsed)

        return reactivex.interval(self._tick_seconds).pipe(
            ops.map(tick_to_state),
            ops.start_with(self._initial_state),
            ops.share(),
        )

    @property
    def initial_state(self) -> ClothSailState:
        return self._initial_state

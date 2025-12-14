import time

import reactivex
from reactivex import operators as ops

from heart.display.renderers.multicolor.state import MulticolorState
from heart.peripheral.core.providers import ObservableProvider


class MulticolorStateProvider(ObservableProvider[MulticolorState]):
    def __init__(self, tick_seconds: float = 1 / 30) -> None:
        self._tick_seconds = tick_seconds

    def observable(self) -> reactivex.Observable[MulticolorState]:
        initial = MulticolorState(timestamp=time.time())

        return reactivex.interval(self._tick_seconds).pipe(
            ops.map(lambda _: MulticolorState(timestamp=time.time())),
            ops.start_with(initial),
            ops.share(),
        )

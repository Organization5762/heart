import reactivex
from reactivex import operators as ops

from heart.display.color import Color
from heart.display.renderers.color.state import RenderColorState
from heart.peripheral.core.providers import ObservableProvider


class RenderColorStateProvider(ObservableProvider[RenderColorState]):
    def __init__(self, color: Color):
        self._color = color

    def observable(self) -> reactivex.Observable[RenderColorState]:
        return reactivex.just(RenderColorState(color=self._color)).pipe(ops.share())

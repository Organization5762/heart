from heart.display.color import Color
from heart.peripheral.core.providers import FixedStateProvider
from heart.renderers.color.state import RenderColorState


class RenderColorStateProvider(FixedStateProvider[RenderColorState]):
    def __init__(self, color: Color):
        super().__init__(RenderColorState(color=color))

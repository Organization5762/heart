from dataclasses import dataclass

from heart.display.color import Color


@dataclass(frozen=True)
class RenderColorState:
    color: Color

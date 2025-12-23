from dataclasses import dataclass

from heart.display.color import Color
from heart.peripheral.switch import SwitchState


@dataclass
class TextRenderingState:
    switch_state: SwitchState | None
    text: tuple[str, ...]
    font_name: str
    font_size: int
    color: Color
    x_location: int | None
    y_location: int | None

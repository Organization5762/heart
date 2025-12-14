from dataclasses import dataclass

from heart.display.color import Color
from heart.peripheral.switch import SwitchState


@dataclass
class YoListenState:
    switch_state: SwitchState | None
    color: Color
    last_flicker_update: float = 0.0
    should_calibrate: bool = True
    scroll_speed_offset: float = 0.0
    word_position: float = 0.0

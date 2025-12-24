from dataclasses import dataclass
from typing import Any

from heart.display.models import KeyFrame
from heart.peripheral.sensor import Acceleration


@dataclass
class MarioRendererState:
    spritesheet: Any
    current_frame: KeyFrame
    current_frame_index: int = 0
    time_since_last_update: float | None = None
    in_loop: bool = False
    highest_z: float = 0.0
    latest_acceleration: Acceleration | None = None
    last_update_time: float | None = None

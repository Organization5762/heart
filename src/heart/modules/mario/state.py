from dataclasses import dataclass
from typing import Any

from heart.peripheral.sensor import Acceleration


@dataclass
class MarioRendererState:
    spritesheet: Any
    current_frame: int = 0
    time_since_last_update: float | None = None
    in_loop: bool = False
    highest_z: float = 0.0
    latest_acceleration: Acceleration | None = None
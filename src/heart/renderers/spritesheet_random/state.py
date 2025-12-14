from dataclasses import dataclass
from enum import StrEnum

from heart.assets.loader import spritesheet as SpritesheetAsset
from heart.peripheral.switch import SwitchState


class LoopPhase(StrEnum):
    START = "start"
    LOOP = "loop"
    END = "end"


@dataclass
class SpritesheetLoopRandomState:
    switch_state: SwitchState | None
    spritesheet: SpritesheetAsset | None = None
    current_frame: int = 0
    loop_count: int = 0
    phase: LoopPhase = LoopPhase.LOOP
    time_since_last_update: float | None = None
    current_screen: int = 0

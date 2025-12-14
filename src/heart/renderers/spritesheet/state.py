from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from heart.peripheral.gamepad.gamepad import Gamepad
from heart.peripheral.switch import SwitchState


@dataclass(frozen=True)
class Size:
    w: int
    h: int


@dataclass(frozen=True)
class BoundingBox(Size):
    x: int
    y: int


@dataclass(frozen=True)
class FrameDescription:
    frame: BoundingBox
    spriteSourceSize: BoundingBox
    sourceSize: Size
    duration: int
    rotated: bool
    trimmed: bool

    @classmethod
    def from_dict(cls, json_data: dict[str, Any]):
        return cls(
            frame=BoundingBox(
                x=json_data["frame"]["x"],
                y=json_data["frame"]["y"],
                w=json_data["frame"]["w"],
                h=json_data["frame"]["h"],
            ),
            spriteSourceSize=BoundingBox(
                x=json_data["spriteSourceSize"]["x"],
                y=json_data["spriteSourceSize"]["y"],
                w=json_data["spriteSourceSize"]["w"],
                h=json_data["spriteSourceSize"]["h"],
            ),
            sourceSize=Size(
                w=json_data["sourceSize"]["w"],
                h=json_data["sourceSize"]["h"],
            ),
            duration=json_data["duration"],
            rotated=json_data["rotated"],
            trimmed=json_data["trimmed"],
        )


class LoopPhase(Enum):
    START = "start"
    LOOP = "loop"
    END = "end"


@dataclass(frozen=True)
class SpritesheetLoopState:
    spritesheet: Any | None = None
    current_frame: int = 0
    loop_count: int = 0
    phase: LoopPhase = LoopPhase.LOOP
    time_since_last_update: float | None = None
    duration_scale: float = 0.0
    last_switch_rotation: float | None = None
    reverse_direction: bool = False
    gamepad: Gamepad | None = None
    switch_state: SwitchState | None = None

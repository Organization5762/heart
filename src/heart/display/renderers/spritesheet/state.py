from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from heart.assets.loader import spritesheet as SpritesheetAsset
from heart.display.models import KeyFrame
from heart.peripheral.gamepad.gamepad import Gamepad


@dataclass
class Size:
    w: int
    h: int


@dataclass
class BoundingBox(Size):
    x: int
    y: int


@dataclass
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


@dataclass
class SpritesheetLoopState:
    spritesheet: SpritesheetAsset | None = None
    current_frame: int = 0
    loop_count: int = 0
    phase: LoopPhase = LoopPhase.LOOP
    time_since_last_update: float | None = None
    duration_scale: float = 0.0
    last_switch_rotation: float | None = None
    reverse_direction: bool = False
    gamepad: Gamepad | None = None


@dataclass
class SpritesheetFrames:
    start: list[KeyFrame]
    loop: list[KeyFrame]
    end: list[KeyFrame]

    @classmethod
    def empty(cls) -> "SpritesheetFrames":
        return cls(start=[], loop=[], end=[])

    def by_phase(self, phase: LoopPhase) -> list[KeyFrame]:
        match phase:
            case LoopPhase.START:
                return self.start
            case LoopPhase.LOOP:
                return self.loop
            case LoopPhase.END:
                return self.end
        return self.loop

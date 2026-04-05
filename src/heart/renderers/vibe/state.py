from dataclasses import dataclass
from pathlib import Path

from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet import (BoundingBox, FrameDescription, Size,
                                         SpritesheetLoop)

TUBE_SHEET_PATH = Path("vibe") / "tube_64x64_spritesheet.png"
TUBE_FRAME_SIZE = 64
TUBE_FRAME_COUNT = 29
TUBE_FRAME_DURATION_MS = 250


@dataclass
class VibeState:
    scenes: list[StatefulBaseRenderer]

    @staticmethod
    def _tube_frame_data() -> list[FrameDescription]:
        return [
            FrameDescription(
                frame=BoundingBox(
                    x=frame_index * TUBE_FRAME_SIZE,
                    y=0,
                    w=TUBE_FRAME_SIZE,
                    h=TUBE_FRAME_SIZE,
                ),
                spriteSourceSize=BoundingBox(
                    x=0,
                    y=0,
                    w=TUBE_FRAME_SIZE,
                    h=TUBE_FRAME_SIZE,
                ),
                sourceSize=Size(w=TUBE_FRAME_SIZE, h=TUBE_FRAME_SIZE),
                duration=TUBE_FRAME_DURATION_MS,
                rotated=False,
                trimmed=False,
            )
            for frame_index in range(TUBE_FRAME_COUNT)
        ]

    @staticmethod
    def build() -> "VibeState":
        scenes: list[StatefulBaseRenderer] = [
            SpritesheetLoop(
                sheet_file_path=str(TUBE_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._tube_frame_data(),
            )
        ]
        return VibeState(scenes=scenes)

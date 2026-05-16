from dataclasses import dataclass
from pathlib import Path

from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet import (BoundingBox, FrameDescription, Size,
                                         SpritesheetLoop)

SUNSLEEPER2_SHEET_PATH = Path("vibe") / "sunsleeper_64x64_spritesheet.png"
TREE_SHEET_PATH = Path("vibe") / "tree_384x384_spritesheet.png"
HEART_SHEET_PATH = Path("vibe") / "heart_64x64_spritesheet.png"
SUN_SHEET_PATH = Path("vibe") / "sun_64x64_spritesheet.png"
SUNSLEEPER2_FRAME_SIZE = 64
SUNSLEEPER2_FRAME_COUNT = 48
SUNSLEEPER2_FRAME_DURATION_MS = 274
TREE_FRAME_SIZE = 384
TREE_FRAME_COUNT = 19
TREE_FRAME_DURATION_MS = 67
HEART_FRAME_SIZE = 64
HEART_FRAME_COUNT = 44
HEART_FRAME_DURATION_MS = 30
SUN_FRAME_SIZE = 64
SUN_FRAME_COUNT = 60
SUN_FRAME_DURATION_MS = 30


@dataclass
class VibeState:
    scenes: list[StatefulBaseRenderer]

    @staticmethod
    def _frame_data(
        frame_size: int,
        frame_count: int,
        duration_ms: int,
    ) -> list[FrameDescription]:
        return [
            FrameDescription(
                frame=BoundingBox(
                    x=frame_index * frame_size,
                    y=0,
                    w=frame_size,
                    h=frame_size,
                ),
                spriteSourceSize=BoundingBox(
                    x=0,
                    y=0,
                    w=frame_size,
                    h=frame_size,
                ),
                sourceSize=Size(w=frame_size, h=frame_size),
                duration=duration_ms,
                rotated=False,
                trimmed=False,
            )
            for frame_index in range(frame_count)
        ]

    @staticmethod
    def build() -> "VibeState":
        scenes: list[StatefulBaseRenderer] = [
            SpritesheetLoop(
                sheet_file_path=str(SUNSLEEPER2_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    SUNSLEEPER2_FRAME_SIZE,
                    SUNSLEEPER2_FRAME_COUNT,
                    SUNSLEEPER2_FRAME_DURATION_MS,
                ),
            ),
            SpritesheetLoop(
                sheet_file_path=str(TREE_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    TREE_FRAME_SIZE,
                    TREE_FRAME_COUNT,
                    TREE_FRAME_DURATION_MS,
                ),
            ),
            SpritesheetLoop(
                sheet_file_path=str(HEART_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    HEART_FRAME_SIZE,
                    HEART_FRAME_COUNT,
                    HEART_FRAME_DURATION_MS,
                ),
            ),
            SpritesheetLoop(
                sheet_file_path=str(SUN_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    SUN_FRAME_SIZE,
                    SUN_FRAME_COUNT,
                    SUN_FRAME_DURATION_MS,
                ),
            ),
        ]
        return VibeState(scenes=scenes)

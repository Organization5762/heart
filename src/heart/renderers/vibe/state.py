from dataclasses import dataclass
from pathlib import Path

from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet import (BoundingBox, FrameDescription, Size,
                                         SpritesheetLoop)

TUBE_SHEET_PATH = Path("vibe") / "tube_64x64_spritesheet.png"
NO_LEGS_SHEET_PATH = Path("vibe") / "no_legs_128x128_spritesheet.png"
SUNSLEEPER_SHEET_PATH = Path("vibe") / "sunsleeper_256x256_spritesheet.png"
SUNSLEEPER2_SHEET_PATH = Path("vibe") / "sunsleeper_64x64_spritesheet.png"
TREE_SHEET_PATH = Path("vibe") / "tree_384x384_spritesheet.png"
TUBE_FRAME_SIZE = 64
TUBE_FRAME_COUNT = 29
TUBE_FRAME_DURATION_MS = 250
NO_LEGS_FRAME_SIZE = 128
NO_LEGS_FRAME_COUNT = 14
NO_LEGS_FRAME_DURATION_MS = 250
SUNSLEEPER_FRAME_SIZE = 256
SUNSLEEPER_FRAME_COUNT = 48
SUNSLEEPER_FRAME_DURATION_MS = 274
SUNSLEEPER2_FRAME_SIZE = 64
SUNSLEEPER2_FRAME_COUNT = 48
SUNSLEEPER2_FRAME_DURATION_MS = 274
TREE_FRAME_SIZE = 384
TREE_FRAME_COUNT = 19
TREE_FRAME_DURATION_MS = 67


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
                sheet_file_path=str(TUBE_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    TUBE_FRAME_SIZE,
                    TUBE_FRAME_COUNT,
                    TUBE_FRAME_DURATION_MS,
                ),
            ),
            SpritesheetLoop(
                sheet_file_path=str(NO_LEGS_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    NO_LEGS_FRAME_SIZE,
                    NO_LEGS_FRAME_COUNT,
                    NO_LEGS_FRAME_DURATION_MS,
                ),
            ),
            SpritesheetLoop(
                sheet_file_path=str(SUNSLEEPER_SHEET_PATH),
                disable_input=True,
                frame_data=VibeState._frame_data(
                    SUNSLEEPER_FRAME_SIZE,
                    SUNSLEEPER_FRAME_COUNT,
                    SUNSLEEPER_FRAME_DURATION_MS,
                ),
            ),
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
        ]
        return VibeState(scenes=scenes)

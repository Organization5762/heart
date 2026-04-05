from heart.display.color import Color
from heart.renderers.spritesheet import (BoundingBox, FrameDescription,
                                         Size, SpritesheetLoop)
from heart.renderers.text import TextRendering
from heart.runtime.game_loop import GameLoop

from .lib_2025 import configure as configure_lib_2025

TUBE_FRAME_SIZE = 64
TUBE_FRAME_COUNT = 29
TUBE_FRAME_DURATION_MS = 250


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


def _build_tube_spritesheet() -> SpritesheetLoop:
    return SpritesheetLoop(
        "tube_64x64_spritesheet.png",
        disable_input=True,
        frame_data=_tube_frame_data(),
    )


def configure(loop: GameLoop) -> None:
    tube_mode = loop.add_mode(
        loop.compose(
            [
                _build_tube_spritesheet(),
                TextRendering(
                    text=["tube"],
                    font="Grand9K Pixel.ttf",
                    font_size=14,
                    color=Color(255, 255, 255),
                    y_location=0.55,
                ),
            ]
        )
    )
    tube_mode.add_renderer(_build_tube_spritesheet())

    configure_lib_2025(loop)

from heart.display.renderers.spritesheet_random import SpritesheetLoopRandom
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    width = 64
    height = 64
    screen_count = 8
    mode.add_renderer(
        SpritesheetLoopRandom(
            screen_width=width,
            screen_height=height,
            screen_count=screen_count,
            sheet_file_path="tvman-sheet.png",
            metadata_file_path="tvman.json",
        )
    )

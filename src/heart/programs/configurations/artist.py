from heart.display.renderers.pixels import Border, RandomPixel
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    renderer = SpritesheetLoop(
        sheet_file_path=f"rainbow_tesseract.png",
        metadata_file_path=f"rainbow_tesseract.json",
        image_scale=1.25,
    )
    mode.add_renderer(renderer)

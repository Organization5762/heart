from heart.renderers.image import RenderImage
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    # mode = loop.add_mode()
    # mode.add_renderer(SpritesheetLoop(
    #     sheet_file_path=f"artist/rainbow_tesseract.png",
    #     metadata_file_path=f"artist/rainbow_tesseract.json",
    #     image_scale=1.25,
    # ))
    mode = loop.add_mode()
    mode.add_renderer(RenderImage(image_file="artist/imaginal_disk.png"))

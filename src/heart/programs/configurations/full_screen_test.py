from heart import DeviceDisplayMode
from heart.renderers.image import RenderImage
from heart.runtime.game_loop import GameLoop

PHOTO_ASSET = "photos/portrait_selfie.png"


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("photo")
    renderer = RenderImage(image_file=PHOTO_ASSET)
    renderer.device_display_mode = DeviceDisplayMode.FULL
    mode.add_renderer(renderer)

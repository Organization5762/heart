from heart.display.renderers.pixels import Border, RandomPixel
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("pixel")
    mode.add_renderer(RandomPixel(num_pixels=200))
    mode.add_renderer(Border(width=2))

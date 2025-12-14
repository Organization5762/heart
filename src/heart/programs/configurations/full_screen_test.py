from heart.environment import GameLoop
from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("pixel")
    mode.add_renderer(RandomPixel(num_pixels=200))
    mode.add_renderer(Border(width=2))

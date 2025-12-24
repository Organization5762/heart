from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("pixel")
    mode.add_renderer(RandomPixel(num_pixels=200))
    mode.add_renderer(Border(width=2))

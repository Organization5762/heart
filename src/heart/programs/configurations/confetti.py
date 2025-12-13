from heart.display.renderers.pixels import Border
from heart.display.renderers.random_pixel import RandomPixel
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(num_pixels=40000, brightness=0.05))
    mode.add_renderer(RandomPixel(num_pixels=4000, brightness=0.10))
    mode.add_renderer(RandomPixel(num_pixels=400, brightness=0.25))
    mode.add_renderer(RandomPixel(num_pixels=40, brightness=0.50))
    mode.add_renderer(RandomPixel(num_pixels=4, brightness=1))
    mode.add_renderer(Border(width=2))

from heart.display.color import Color
from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.display.renderers.pixels import Border, RandomPixel
from heart.display.renderers.pacman import PacmanGhostRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(num_pixels=40000, brightness=0.05))
    mode.add_renderer(RandomPixel(num_pixels=4000, brightness=0.10))
    mode.add_renderer(RandomPixel(num_pixels=400, brightness=0.25))
    mode.add_renderer(RandomPixel(num_pixels=40, brightness=0.50))
    mode.add_renderer(RandomPixel(num_pixels=4, brightness=1))
    mode.add_renderer(Border(width=2))

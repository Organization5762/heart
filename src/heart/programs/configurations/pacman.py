from heart.display.color import Color
from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.display.renderers.pixels import Border, RandomPixel
from heart.display.renderers.pacman import PacmanGhostRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    for _ in range(0, 50):
        mode.add_renderer(RandomPixel())
    mode.add_renderer(PacmanGhostRenderer())
    mode.add_renderer(Border(width=2))

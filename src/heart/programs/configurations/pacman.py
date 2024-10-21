from heart.display.color import Color
from heart.display.renderers.pacman import PacmanGhostRenderer
from heart.display.renderers.pixels import Border, RandomPixel
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(color=Color(187, 10, 30), num_pixels=50))
    mode.add_renderer(PacmanGhostRenderer())
    mode.add_renderer(Border(width=2, color=Color(187, 10, 30)))

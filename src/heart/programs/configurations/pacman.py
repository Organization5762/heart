from heart.display.color import Color
from heart.environment import GameLoop
from heart.renderers.pacman import PacmanGhostRenderer
from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(color=Color(187, 10, 30), num_pixels=50))
    mode.resolve_renderer(loop.context_container, PacmanGhostRenderer)
    mode.add_renderer(Border(width=2, color=Color(187, 10, 30)))

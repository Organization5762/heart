from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(MandelbrotMode(64, 64))
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(MandelbrotMode())

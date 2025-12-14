from heart.environment import GameLoop
from heart.renderers.mandelbrot.scene import MandelbrotMode


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(MandelbrotMode())

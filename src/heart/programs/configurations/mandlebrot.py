from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(MandelbrotMode)

from heart.environment import GameLoop
from heart.renderers.mandelbrot.scene import MandelbrotMode


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.resolve_renderer(loop.context_container, MandelbrotMode)

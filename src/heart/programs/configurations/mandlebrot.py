from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.resolve_renderer(loop.context_container, MandelbrotMode)

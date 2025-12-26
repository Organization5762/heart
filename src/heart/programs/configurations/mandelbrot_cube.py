from heart.renderers.mandelbrot.cube_renderer import CubeMandelbrotRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("mandelbrot cube")
    mode.resolve_renderer_from_container(CubeMandelbrotRenderer)

from heart.renderers.three_fractal import FractalScene
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    sphere_mode = loop.add_mode("3d fractal")
    sphere_mode.resolve_renderer_from_container(FractalScene)

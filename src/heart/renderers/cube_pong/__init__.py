from heart.renderers.cube_pong.renderer import CubePongRenderer
from heart.runtime.game_loop import GameLoop


def add_cube_pong_mode(loop: GameLoop) -> None:
    mode = loop.add_mode("cube\npong")
    mode.add_renderer(CubePongRenderer())

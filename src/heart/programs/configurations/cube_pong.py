from heart.renderers.cube_pong import add_cube_pong_mode
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    add_cube_pong_mode(loop)

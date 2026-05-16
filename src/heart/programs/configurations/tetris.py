from heart.renderers.tetris import TetrisRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("tetris")
    mode.add_renderer(TetrisRenderer())
    loop.components.game_modes.state.in_select_mode = False
    loop.components.game_modes.state.post_processors.clear()

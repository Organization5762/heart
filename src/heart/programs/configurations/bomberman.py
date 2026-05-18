from heart.renderers.bomberman import BombermanRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode(title="Bomberman")
    mode.add_renderer(BombermanRenderer)
    loop.components.game_modes.state._active_mode_index = 0
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False
    loop.components.game_modes.disable_navigation()

"""Static Kirby title card for HUB75/base-image diagnostics."""

from heart.renderers.kirby import KirbyScene
from heart.runtime.game_loop import GameLoop

KIRBY_TITLE_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    loop.add_mode(KirbyScene.title_scene())
    loop.components.game_modes.state._active_mode_index = KIRBY_TITLE_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = True

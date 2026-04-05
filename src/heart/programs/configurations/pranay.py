from heart.renderers.pranay_sketch import PranaySketchRenderer
from heart.runtime.game_loop import GameLoop

DOLLYS_SKETCH_MODE_TITLE = "Dolly's\nsketch"
PRANAY_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    pranay_mode = loop.add_mode(DOLLYS_SKETCH_MODE_TITLE)
    pranay_mode.add_renderer(PranaySketchRenderer())
    loop.components.game_modes.state._active_mode_index = PRANAY_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

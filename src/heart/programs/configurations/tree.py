from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.vibe.state import (TREE_FRAME_COUNT,
                                        TREE_FRAME_DURATION_MS,
                                        TREE_FRAME_SIZE, TREE_SHEET_PATH,
                                        VibeState)
from heart.runtime.game_loop import GameLoop

TREE_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    tree_mode = loop.add_mode("tree")
    tree_mode.add_renderer(
        SpritesheetLoop(
            sheet_file_path=str(TREE_SHEET_PATH),
            disable_input=True,
            frame_data=VibeState._frame_data(
                TREE_FRAME_SIZE,
                TREE_FRAME_COUNT,
                TREE_FRAME_DURATION_MS,
            ),
        )
    )
    loop.components.game_modes.state._active_mode_index = TREE_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

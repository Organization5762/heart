from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.vibe.state import (HEART_FRAME_COUNT,
                                        HEART_FRAME_DURATION_MS,
                                        HEART_FRAME_SIZE, HEART_SHEET_PATH,
                                        VibeState)
from heart.runtime.game_loop import GameLoop

HEART_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    heart_mode = loop.add_mode("heart")
    heart_mode.add_renderer(
        SpritesheetLoop(
            sheet_file_path=str(HEART_SHEET_PATH),
            disable_input=True,
            frame_data=VibeState._frame_data(
                HEART_FRAME_SIZE,
                HEART_FRAME_COUNT,
                HEART_FRAME_DURATION_MS,
            ),
        )
    )
    loop.components.game_modes.state._active_mode_index = HEART_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

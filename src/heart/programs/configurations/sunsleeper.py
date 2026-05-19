from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.vibe.state import (SUNSLEEPER2_FRAME_COUNT,
                                        SUNSLEEPER2_FRAME_DURATION_MS,
                                        SUNSLEEPER2_FRAME_SIZE,
                                        SUNSLEEPER2_SHEET_PATH, VibeState)
from heart.runtime.game_loop import GameLoop

SUNSLEEPER_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    sunsleeper_mode = loop.add_mode("sunsleeper")
    sunsleeper_mode.add_renderer(
        SpritesheetLoop(
            sheet_file_path=str(SUNSLEEPER2_SHEET_PATH),
            disable_input=True,
            frame_data=VibeState._frame_data(
                SUNSLEEPER2_FRAME_SIZE,
                SUNSLEEPER2_FRAME_COUNT,
                SUNSLEEPER2_FRAME_DURATION_MS,
            ),
        )
    )
    loop.components.game_modes.state._active_mode_index = SUNSLEEPER_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

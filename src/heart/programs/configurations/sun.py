from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.vibe.state import SUN_SHEET_PATH
from heart.runtime.game_loop import GameLoop

SUN_MODE_INDEX = 0
SUN_OLD_RENDERER_DURATION_MS = 30
SUN_BRIGHTNESS = 0.5


def configure(loop: GameLoop) -> None:
    sun_mode = loop.add_mode("sun")
    sun_mode.add_renderer(
        SpritesheetLoop.from_frame_data(
            sheet_file_path=str(SUN_SHEET_PATH),
            duration=SUN_OLD_RENDERER_DURATION_MS,
            disable_input=True,
        ).brightness(SUN_BRIGHTNESS)
    )
    loop.components.game_modes.state._active_mode_index = SUN_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

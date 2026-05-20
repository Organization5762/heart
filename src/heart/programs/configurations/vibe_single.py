import os

from heart.renderers.vibe.state import VibeState
from heart.runtime.game_loop import GameLoop

VIBE_SINGLE_MODE_INDEX = 0
VIBE_SCENE_NAMES = (
    "sunsleeper",
    "tree",
    "heart",
    "flower",
    "zed",
    "sun",
    "space",
    "overmono sheet",
    "overmono runner",
    "sara",
    "oppi",
    "berry preserver",
)


def configure(loop: GameLoop) -> None:
    vibe_state = VibeState.build()
    scene_index = selected_scene_index(len(vibe_state.scenes))
    mode = loop.add_mode(f"vibe {VIBE_SCENE_NAMES[scene_index]}")
    mode.add_renderer(vibe_state.scenes[scene_index])
    loop.components.game_modes.state._active_mode_index = VIBE_SINGLE_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False


def selected_scene_index(scene_count: int) -> int:
    raw_index = os.environ.get("HEART_VIBE_SCENE_INDEX", "0")
    try:
        scene_index = int(raw_index)
    except ValueError:
        scene_index = 0
    return max(0, min(scene_count - 1, scene_index))

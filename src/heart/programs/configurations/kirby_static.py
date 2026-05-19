"""Single static Kirby spritesheet image for panel/driver isolation."""

import os

from heart import DeviceDisplayMode
from heart.renderers.image import ContainRenderImage
from heart.runtime.game_loop import GameLoop

KIRBY_STATIC_ASSET = "kirby_flying_32.png"
KIRBY_STATIC_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    asset = os.environ.get("HEART_KIRBY_STATIC_ASSET", KIRBY_STATIC_ASSET)
    mode = loop.add_mode("kirby static")
    renderer = ContainRenderImage(image_file=asset)
    renderer.device_display_mode = DeviceDisplayMode.MIRRORED
    mode.add_renderer(renderer)

    loop.components.game_modes.state._active_mode_index = KIRBY_STATIC_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

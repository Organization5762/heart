"""Single mirrored still image that fits fully within each panel."""

from heart import DeviceDisplayMode
from heart.renderers.image import ContainRenderImage
from heart.runtime.game_loop import GameLoop

PHOTO_ASSET = "photos/portrait_selfie.png"
PHOTO_MODE_INDEX = 0


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("photo")
    renderer = ContainRenderImage(image_file=PHOTO_ASSET)
    renderer.device_display_mode = DeviceDisplayMode.MIRRORED
    mode.add_renderer(renderer)
    # Skip mode-selection UI; otherwise only the "photo" title renders on the matrix.
    loop.components.game_modes.state._active_mode_index = PHOTO_MODE_INDEX
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False

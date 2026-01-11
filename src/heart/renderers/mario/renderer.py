

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.mario.provider import MarioRendererProvider
from heart.renderers.mario.state import MarioRendererState
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)



class MarioRenderer(StatefulBaseRenderer[MarioRendererState]):
    def __init__(
        self,
        builder: MarioRendererProvider,
    ) -> None:
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        screen_width, screen_height = window.get_size()
        # TODO:
        scaled = self.state.spritesheet.image_at_scaled(
            (0,0,64,64), (screen_width, screen_height)
        )
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        window.blit(scaled, (center_x, center_y))


import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.modules.mario.provider import MarioRendererProvider
from heart.modules.mario.state import MarioRendererState
from heart.renderers import StatefulBaseRenderer
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
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        screen_width, screen_height = window.get_size()
        image = self.state.spritesheet.image_at(self.state.current_frame.frame)
        scaled = pygame.transform.scale(image, (screen_width, screen_height))
        center_x = (screen_width - scaled.get_width()) // 2
        center_y = (screen_height - scaled.get_height()) // 2

        window.blit(scaled, (center_x, center_y))
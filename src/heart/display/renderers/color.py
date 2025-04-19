import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


class RenderColor(BaseRenderer):
    def __init__(self, color: Color) -> None:
        super().__init__()
        self.color = color

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> None:
        image = pygame.Surface(window.get_size())
        image.fill(self.color._as_tuple())
        window.blit(image, (0, 0))

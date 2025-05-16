import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class RenderImage(BaseRenderer):
    def __init__(self, image_file: str) -> None:
        super().__init__()
        self.current_frame = 0
        self.file = image_file
        self.image = None

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.image = Loader.load(self.file)
        self.image = pygame.transform.scale(self.image, window.get_size())
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        window.blit(self.image, (0, 0))

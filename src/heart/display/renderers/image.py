import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.models import KeyFrame
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class RenderImage(BaseRenderer):
    def __init__(self, image_file: str) -> None:
        super().__init__()
        self.initialized = False
        self.current_frame = 0
        self.file = image_file

    def _initialize(self) -> None:
        self.image = Loader.load(self.file)
        self.initialized = True

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.initialized:
            self._initialize()
            self.image = pygame.transform.scale(self.image, window.get_size())

        window.blit(self.image, (0, 0))

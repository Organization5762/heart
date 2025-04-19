from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0


class RenderImage(BaseRenderer):
    def __init__(self, image_file: str) -> None:
        super().__init__()
        self.initialized = False
        self.current_frame = 0
        self.file = Loader._resolve_path(image_file)

    def _initialize(self) -> None:
        self.spritesheet = Loader.load_spirtesheet(self.file)
        self.initialized = True

    def process(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> None:
        if not self.initialized:
            self._initialize()

        image = self.spritesheet.image_at(
            KeyFrame(
                (0, 0, 28, 28),
            ).frame
        )
        window.blit(image, (0, 0))

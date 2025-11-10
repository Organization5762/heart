from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class RenderImageState:
    image: pygame.Surface | None = None


class RenderImage(AtomicBaseRenderer[RenderImageState]):
    def __init__(self, image_file: str) -> None:
        self._image_file = image_file
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(self) -> RenderImageState:
        return RenderImageState()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        image = Loader.load(self._image_file).convert_alpha()
        image = pygame.transform.scale(image, window.get_size())
        self.update_state(image=image)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.state.image is None:
            return
        window.blit(self.state.image, (0, 0))

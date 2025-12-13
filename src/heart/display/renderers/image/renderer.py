import pygame
import reactivex

from heart.device import Orientation
from heart.display.renderers import StatefulBaseRenderer
from heart.display.renderers.image.provider import RenderImageStateProvider
from heart.display.renderers.image.state import RenderImageState
from heart.peripheral.core.manager import PeripheralManager


class RenderImage(StatefulBaseRenderer[RenderImageState]):
    """Render an image sourced from an asset file or a renderer event stream."""

    def __init__(self, image_file: str) -> None:
        super().__init__(builder=RenderImageStateProvider(image_file=image_file))

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[RenderImageState]:
        return self.builder.observable(peripheral_manager=peripheral_manager)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        window.blit(self.state.image, (0, 0))

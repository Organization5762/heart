import pygame
import reactivex

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.image.provider import RenderImageStateProvider
from heart.renderers.image.state import RenderImageState


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

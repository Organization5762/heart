from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.runtime.display_context import DisplayContext


@dataclass
class MandelbrotTitleState:
    image: pygame.Surface


class MandelbrotTitle(StatefulBaseRenderer[MandelbrotTitleState]):
    def __init__(self):
        super().__init__()
        # Match the real Mandelbrot scene geometry so the preview is framed
        # the same way as the mode users enter from the selector.
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> MandelbrotTitleState:
        mandelbrot = MandelbrotMode()
        mandelbrot.initialize(
            window,
            peripheral_manager,
            orientation,
        )
        mandelbrot._internal_process(
            window,
            peripheral_manager,
            orientation,
        )
        first_image = window.screen.copy()
        return MandelbrotTitleState(image=first_image)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        window.blit(self.state.image, (0, 0))

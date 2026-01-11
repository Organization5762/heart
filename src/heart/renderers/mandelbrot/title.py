from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
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
        self.mandelbrot = MandelbrotMode()
        # Avoid double mirroring by setting this display
        # to just take in the full screen
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> MandelbrotTitleState:
        custom_orientation = Rectangle.with_layout(1, 1)
        self.mandelbrot.initialize(
            window,
            peripheral_manager,
            custom_orientation,
        )
        self.mandelbrot._internal_process(
            window, peripheral_manager, custom_orientation
        )
        first_image = window.screen.copy()
        del self.mandelbrot
        self.mandelbrot = None
        return MandelbrotTitleState(image=first_image)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        window.blit(self.state.image, (0, 0))

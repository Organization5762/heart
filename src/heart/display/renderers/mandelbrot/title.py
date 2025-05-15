from heart import DeviceDisplayMode
from heart.device import Rectangle
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
import pygame
from heart.peripheral.core.manager import PeripheralManager
from heart.device import Orientation

class MandelbrotTitle(MandelbrotMode):
    def __init__(self):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.first_image = None

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        super().initialize(window, clock, peripheral_manager, orientation)
        if self.first_image is None:
            super()._internal_process(
                window, clock, peripheral_manager, Rectangle.with_layout(1, 1)
            )
            self.first_image = window.copy()

    def process(self, window, clock, peripheral_manager, orientation):
        window.blit(self.first_image, (0, 0))

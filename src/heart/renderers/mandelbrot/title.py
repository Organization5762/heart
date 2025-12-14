import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import BaseRenderer
from heart.renderers.mandelbrot.scene import MandelbrotMode


class MandelbrotTitle(BaseRenderer):
    def __init__(self):
        super().__init__()
        self.mandelbrot = MandelbrotMode()
        # Avoid double mirroring by setting this display
        # to just take in the full screen
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.first_image = None

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        custom_orientation = Rectangle.with_layout(1, 1)
        if self.first_image is None:
            self.mandelbrot._internal_process(
                window, clock, peripheral_manager, custom_orientation
            )
            self.first_image = window.copy()
            del self.mandelbrot
            self.mandelbrot = None
        super().initialize(window, clock, peripheral_manager, custom_orientation)

    def process(self, window, clock, peripheral_manager, orientation):
        window.blit(self.first_image, (0, 0))

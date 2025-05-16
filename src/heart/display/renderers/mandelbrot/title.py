import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.display.renderers import BaseRenderer
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.peripheral.core.manager import PeripheralManager


class MandelbrotTitle(BaseRenderer):
    def __init__(self):
        super().__init__()
        self.mandle = MandelbrotMode()
        # Avoid double mirroring by setting this display
        # to just take in the full screen
        self.device_display_mode = DeviceDisplayMode.FULL
        self.first_image = None

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        if self.first_image is None:
            self.mandle._internal_process(
                window, clock, peripheral_manager, orientation
            )
            self.first_image = window.copy()
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(self, window, clock, peripheral_manager, orientation):
        window.blit(self.first_image, (0, 0))

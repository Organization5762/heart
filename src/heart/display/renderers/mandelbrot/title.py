from heart import DeviceDisplayMode
from heart.device import Rectangle
from heart.display.renderers.mandelbrot.scene import MandelbrotMode


class MandelbrotTitle(MandelbrotMode):
    def __init__(self):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.first_image = None

    def process(self, window, clock, peripheral_manager, orientation):
        if self.first_image is None:
            super().process(
                window, clock, peripheral_manager, Rectangle.with_layout(1, 1)
            )
            self.first_image = window.copy()

        window.blit(self.first_image, (0, 0))

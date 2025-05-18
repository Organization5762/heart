import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class SlidingImage(BaseRenderer):
    """Render a 256×64 image that continuously slides horizontally.

    The renderer operates in *FULL* display mode so it receives the complete
    256×64 surface (four 64×64 cube faces laid out left→right).
    Each frame the image is shifted `speed` pixels to the **left**; once the
    offset reaches the image width it wraps to 0, creating an endless loop
    around the cube sides.

    """

    def __init__(self, image_file: str, *, speed: int = 1) -> None:
        super().__init__()
        # We want to draw across the full 4-face surface
        self.device_display_mode = DeviceDisplayMode.FULL

        self.file = image_file
        self.image: pygame.Surface | None = None  # will be loaded at init

        # slide state
        self._offset = 0  # current left-shift in pixels
        self._speed = max(1, speed)  # guard against 0 / negative speeds

    # ---------------------------------------------------------------------
    # lifecycle hooks
    # ---------------------------------------------------------------------
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # load and scale once we know the LED surface size
        self.image = Loader.load(self.file)
        self.image = pygame.transform.scale(self.image, window.get_size())
        super().initialize(window, clock, peripheral_manager, orientation)

    # ---------------------------------------------------------------------
    # main draw routine
    # ---------------------------------------------------------------------
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.image is None:
            # should not happen – initialize() guarantees loading
            return

        img_w, _ = self.image.get_size()

        # advance offset and wrap
        self._offset = (self._offset + self._speed) % img_w

        # First blit: main image shifted left by current offset
        window.blit(self.image, (-self._offset, 0))

        # Second blit: fill the gap on the right with the wrapped part
        if self._offset:
            window.blit(self.image, (img_w - self._offset, 0))

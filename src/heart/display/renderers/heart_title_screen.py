import time

from pygame import Surface, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400
logger = get_logger("HeartRateTitleScreen")


class HeartTitleScreen(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.current_frame = 0

        # Load blue heart images
        self.heart_images = {
            "small": Loader.load("hearts/blue/small.png"),
            "med": Loader.load("hearts/blue/med.png"),
            "big": Loader.load("hearts/blue/big.png"),
        }

        # Heart animation state
        self.heart_up = True
        self.last_update = 0
        self.time_between_beats = 500  # Default timing (ms)

    def display_number(self, window, number, x, y):
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y))
        window.blit(text, text_rect)

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Get window dimensions
        window_width, window_height = window.get_size()

        # Update animation state
        self.last_update += clock.get_time()

        if self.last_update > DEFAULT_TIME_BETWEEN_FRAMES_MS:
            self.last_update = 0
            self.heart_up = not self.heart_up

        # Determine which image to use based on animation state
        image_key = "small" if self.heart_up else "med"
        image = self.heart_images[image_key]

        # Center the heart in the window
        image_width, image_height = image.get_size()
        heart_x = (window_width - image_width) // 2
        heart_y = (window_height - image_height) // 2 - 20

        # Clear the window
        window.fill((0, 0, 0))

        # Draw the heart
        window.blit(image, (heart_x, heart_y))

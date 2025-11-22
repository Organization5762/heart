from dataclasses import dataclass

import pygame
from pygame import Surface, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400
logger = get_logger("HeartRateTitleScreen")


@dataclass
class HeartTitleScreenState:
    heart_up: bool = True
    elapsed_ms: float = 0.0


class HeartTitleScreen(AtomicBaseRenderer[HeartTitleScreenState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

        # Load blue heart images
        self.heart_images = {
            "small": Loader.load("hearts/blue/small.png"),
            "med": Loader.load("hearts/blue/med.png"),
            "big": Loader.load("hearts/blue/big.png"),
        }

    def display_number(self, window, number, x, y):
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y))
        window.blit(text, text_rect)

    def real_process(
        self,
        window: Surface,
        clock: time.Clock,
        orientation: Orientation,
    ) -> None:
        # Get window dimensions
        window_width, window_height = window.get_size()

        # Update animation state
        # TODO: Move clock into _create_initial_state callbacks
        state = self.state
        elapsed_ms = state.elapsed_ms + clock.get_time()
        heart_up = state.heart_up

        if elapsed_ms > DEFAULT_TIME_BETWEEN_FRAMES_MS:
            elapsed_ms = 0
            heart_up = not heart_up

        if heart_up != state.heart_up or elapsed_ms != state.elapsed_ms:
            self.update_state(heart_up=heart_up, elapsed_ms=elapsed_ms)

        # Determine which image to use based on animation state
        image_key = "small" if heart_up else "med"
        image = self.heart_images[image_key]

        # Center the heart in the window
        image_width, image_height = image.get_size()
        heart_x = (window_width - image_width) // 2
        heart_y = (window_height - image_height) // 2 - 20

        # Clear the window
        window.fill((0, 0, 0))

        # Draw the heart
        window.blit(image, (heart_x, heart_y))

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> HeartTitleScreenState:
        return HeartTitleScreenState()

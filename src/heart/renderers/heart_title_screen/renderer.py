from pygame import Surface, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.heart_title_screen.provider import \
    HeartTitleScreenStateProvider
from heart.renderers.heart_title_screen.state import HeartTitleScreenState
from heart.runtime.display_context import DisplayContext


class HeartTitleScreen(StatefulBaseRenderer[HeartTitleScreenState]):
    def __init__(self, builder: HeartTitleScreenStateProvider) -> None:
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.MIRRORED

        # Load blue heart images
        self.heart_images = {
            "small": Loader.load("hearts/blue/small.png"),
            "med": Loader.load("hearts/blue/med.png"),
            "big": Loader.load("hearts/blue/big.png"),
        }

    def display_number(self, window: Surface, number, x, y):
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(x, y))
        window.blit(text, text_rect)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        # Get window dimensions
        window_width, window_height = window.get_size()

        state = self.state

        # Determine which image to use based on animation state
        image_key = "small" if state.heart_up else "med"
        image = self.heart_images[image_key]

        # Center the heart in the window
        image_width, image_height = image.get_size()
        heart_x = (window_width - image_width) // 2
        heart_y = (window_height - image_height) // 2 - 20

        # Clear the window
        window.fill((0, 0, 0))

        # Draw the heart
        window.blit(image, (heart_x, heart_y))

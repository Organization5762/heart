from typing import Any

import pygame
from PIL import Image

from heart.device import Device, Layout, Orientation
from heart.device.rgb_display.sample_base import SampleBase
from heart.device.rgb_display.worker import MatrixDisplayWorker
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class LEDMatrix(Device, SampleBase):
    def __init__(self, orientation: Orientation, *args: Any, **kwargs: Any) -> None:
        Device.__init__(self, orientation=orientation)
        SampleBase.__init__(self, *args, **kwargs)

        self.chain_length = orientation.layout.columns
        self.parallel = orientation.layout.rows
        self.row_size = Configuration.panel_rows()
        self.col_size = Configuration.panel_columns()

        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()
        options.rows = self.row_size
        options.cols = self.col_size
        options.chain_length = self.chain_length
        options.parallel = self.parallel
        options.pwm_bits = 11

        options.show_refresh_rate = 1
        # Setting this to True can cause ghosting
        options.disable_hardware_pulsing = False
        options.multiplexing = 0
        options.row_address_type = 0
        options.brightness = 100
        options.led_rgb_sequence = "RGB"

        # These two settings, pwm_lsb_nanoseconds and gpio_slowdown are sometimes associated with ghosting
        # https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/README.md
        options.pwm_lsb_nanoseconds = 100
        options.gpio_slowdown = 4
        options.pixel_mapper_config = ""
        options.panel_type = ""
        # I hate this option.
        options.drop_privileges = False

        self.matrix = RGBMatrix(options=options)
        self.worker = MatrixDisplayWorker(self.matrix)

    def layout(self) -> Layout:
        return Layout(columns=self.chain_length, rows=self.parallel)

    def individual_display_size(self) -> tuple[int, int]:
        return (self.col_size, self.row_size)

    def full_display_size(self) -> tuple[int, int]:
        return (self.col_size * self.chain_length, self.row_size * self.parallel)

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode

    def set_screen(self, screen: pygame.Surface) -> None:
        image_bytes = pygame.image.tostring(screen, RGBA_IMAGE_FORMAT)
        image = Image.frombuffer(
            RGBA_IMAGE_FORMAT,
            screen.get_size(),
            image_bytes,
            "raw",
            RGBA_IMAGE_FORMAT,
            0,
            1,
        )
        self.set_image(image)

    def set_image(self, image: Image.Image) -> None:
        self.worker.set_image_async(image)

from __future__ import annotations

import atexit
from typing import Any

import pygame
from PIL import Image

from heart.device import Device, Layout, Orientation
from heart.device.rgb_display.runtime import (MatrixDriverProtocol,
                                              build_matrix_driver)
from heart.runtime.rendering.constants import RGBA_IMAGE_FORMAT
from heart.utilities.env import Configuration


class LEDMatrix(Device):
    def __init__(self, orientation: Orientation, *args: Any, **kwargs: Any) -> None:
        del args
        del kwargs
        super().__init__(orientation=orientation)
        self.chain_length = orientation.layout.columns
        self.parallel = orientation.layout.rows
        self.row_size = Configuration.panel_rows()
        self.col_size = Configuration.panel_columns()
        self.driver: MatrixDriverProtocol = build_matrix_driver(orientation)
        atexit.register(self.close)

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
        width, height = screen.get_size()
        self.driver.submit_rgba(image_bytes, width, height)

    def set_image(self, image: Image.Image) -> None:
        converted_image = image.convert(RGBA_IMAGE_FORMAT)
        self.driver.submit_rgba(
            converted_image.tobytes(),
            converted_image.width,
            converted_image.height,
        )

    def close(self) -> None:
        self.driver.close()

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
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
FRAME_LOG_INTERVAL = 120
STARTUP_FLUSH_FRAMES = 3


class LEDMatrix(Device):
    def __init__(self, orientation: Orientation, *args: Any, **kwargs: Any) -> None:
        del args
        del kwargs
        super().__init__(orientation=orientation)
        self.chain_length = orientation.layout.columns
        self.parallel = orientation.layout.rows
        self.row_size = Configuration.panel_rows()
        self.col_size = Configuration.panel_columns()
        logger.info(
            "Initializing LEDMatrix rows=%s cols=%s chain_length=%s parallel=%s full_size=%s",
            self.row_size,
            self.col_size,
            self.chain_length,
            self.parallel,
            self.full_display_size(),
        )
        self.driver: MatrixDriverProtocol = build_matrix_driver(orientation)
        self._frames_sent = 0
        self._flush_startup_frames()
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
        self._frames_sent += 1
        if self._frames_sent == 1 or self._frames_sent % FRAME_LOG_INTERVAL == 0:
            average_color = pygame.transform.average_color(screen)
            logger.info(
                "Sending matrix frame #%s size=%s avg_rgba=%s",
                self._frames_sent,
                screen.get_size(),
                average_color,
            )
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

    def _flush_startup_frames(self) -> None:
        logger.info("Flushing matrix startup state with %s black frames", STARTUP_FLUSH_FRAMES)
        self.driver.clear()
        width, height = self.full_display_size()
        blank_frame = bytes(width * height * len(RGBA_IMAGE_FORMAT))
        for _ in range(STARTUP_FLUSH_FRAMES):
            self.driver.submit_rgba(blank_frame, width, height)

    def close(self) -> None:
        self.driver.close()

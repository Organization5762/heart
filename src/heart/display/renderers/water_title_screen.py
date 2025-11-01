import math
import time

import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400

logger = get_logger("WaterTitleScreen")


class WaterTitleScreen(BaseRenderer):
    """A simple water animation title screen with water moving from left to right."""

    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.face_px = 64  # physical LED face resolution
        self.cube_px_w = self.face_px * 4  # 256
        self.cube_px_h = self.face_px  # 64
        self.water_level = self.face_px // 2  # Half full
        self.wave_offset = 0  # Current wave position
        self.wave_speed = 0.5  # Speed of wave movement
        self.wave_height = 5  # Height of wave in pixels
        self.wave_length = self.face_px * 1.5  # Length of wave

        # Water color (blue)
        self.water_color = (0, 90, 255)

        # Time tracking
        self.last_frame_time = time.time()

    def _generate_wave_height(self, x: int) -> float:
        """Generate height of wave at position x."""
        wave_pos = (x + self.wave_offset) % (self.cube_px_w * 2)
        # Sine wave for water surface
        wave = math.sin(wave_pos * 2 * math.pi / self.wave_length) * self.wave_height
        return self.water_level + wave

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Update animation
        current_time = time.time()
        elapsed = current_time - self.last_frame_time
        self.last_frame_time = current_time

        # Move the wave
        self.wave_offset += self.wave_speed * elapsed * 60  # Scale by expected 60fps

        # Clear the window
        window.fill((0, 0, 0))

        # Render directly to the window
        for x in range(self.cube_px_w):
            height = int(self._generate_wave_height(x))
            # Draw water column
            if height > 0:
                pygame.draw.line(
                    window,
                    self.water_color,
                    (x, self.cube_px_h - height),
                    (x, self.cube_px_h - 1),
                    1,
                )

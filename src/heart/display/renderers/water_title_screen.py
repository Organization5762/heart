import math
import time
from dataclasses import dataclass

import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400

logger = get_logger("WaterTitleScreen")


@dataclass(frozen=True)
class WaterTitleScreenState:
    wave_offset: float
    last_frame_time: float


class WaterTitleScreen(AtomicBaseRenderer[WaterTitleScreenState]):
    """A simple water animation title screen with water moving from left to right."""

    def __init__(self) -> None:
        self.face_px = 64  # physical LED face resolution
        self.cube_px_w = self.face_px * 4  # 256
        self.cube_px_h = self.face_px  # 64
        self.water_level = self.face_px // 2  # Half full
        self.wave_speed = 0.5  # Speed of wave movement
        self.wave_height = 5  # Height of wave in pixels
        self.wave_length = self.face_px * 1.5  # Length of wave

        # Water color (blue)
        self.water_color = (0, 90, 255)

        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(self) -> WaterTitleScreenState:
        return WaterTitleScreenState(wave_offset=0.0, last_frame_time=time.time())

    def _generate_wave_height(self, x: int, wave_offset: float) -> float:
        """Generate height of wave at position x."""
        wave_pos = (x + wave_offset) % (self.cube_px_w * 2)
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
        state = self.state
        current_time = time.time()
        elapsed = current_time - state.last_frame_time
        updated_wave_offset = state.wave_offset + self.wave_speed * elapsed * 60

        self.update_state(wave_offset=updated_wave_offset, last_frame_time=current_time)

        # Clear the window
        window.fill((0, 0, 0))

        # Render directly to the window
        for x in range(self.cube_px_w):
            height = int(self._generate_wave_height(x, updated_wave_offset))
            # Draw water column
            if height > 0:
                pygame.draw.line(
                    window,
                    self.water_color,
                    (x, self.cube_px_h - height),
                    (x, self.cube_px_h - 1),
                    1,
                )

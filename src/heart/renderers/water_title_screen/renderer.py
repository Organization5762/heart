import math

import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.renderers.water_title_screen.provider import \
    WaterTitleScreenStateProvider
from heart.renderers.water_title_screen.state import WaterTitleScreenState


class WaterTitleScreen(StatefulBaseRenderer[WaterTitleScreenState]):
    """A simple water animation title screen with water moving from left to right."""

    def __init__(self, builder: WaterTitleScreenStateProvider) -> None:
        super().__init__(builder=builder)
        self.face_px = 64  # physical LED face resolution
        self.cube_px_w = self.face_px * 4  # 256
        self.cube_px_h = self.face_px  # 64
        self.water_level = self.face_px // 2  # Half full
        self.wave_height = 5  # Height of wave in pixels
        self.wave_length = self.face_px * 1.5  # Length of wave

        # Water color (blue)
        self.water_color = (0, 90, 255)

        self.device_display_mode = DeviceDisplayMode.FULL

    def _generate_wave_height(self, x: int, wave_offset: float) -> float:
        """Generate height of wave at position x."""
        wave_pos = (x + wave_offset) % (self.cube_px_w * 2)
        wave = math.sin(wave_pos * 2 * math.pi / self.wave_length) * self.wave_height
        return self.water_level + wave

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        wave_offset = self.state.wave_offset

        window.fill((0, 0, 0))

        for x in range(self.cube_px_w):
            height = int(self._generate_wave_height(x, wave_offset))
            if height > 0:
                pygame.draw.line(
                    window,
                    self.water_color,
                    (x, self.cube_px_h - height),
                    (x, self.cube_px_h - 1),
                    1,
                )

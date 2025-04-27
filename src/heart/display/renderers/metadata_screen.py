import logging
import time

from pygame import Surface, time

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.heart_rates import current_bpms
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400

logger = get_logger("HeartRateManager")


class MetadataScreen(BaseRenderer):
    def __init__(self, x, y, color, heart_rate_id) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.current_frame = 0
        self.color = color
        self.small_heart_image = Loader.load(f"hearts/{self.color}/small.png")
        self.med_heart_image = Loader.load(f"hearts/{self.color}/med.png")
        self.big_heart_image = Loader.load(f"hearts/{self.color}/big.png")
        self.image = self.small_heart_image

        self.time_since_last_update = None
        self.time_between_frames_ms = DEFAULT_TIME_BETWEEN_FRAMES_MS
        self.time_since_last_update = 0

        self.heart_rate_id = heart_rate_id
        self.up = True

        self.x = x
        self.y = y

    def display_number(self, window, number):
        my_font = Loader.load_font("Grand9K Pixel.ttf")
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + 16, self.y + 25))
        window.blit(text, text_rect)

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Get current BPM and update time_between_frames_ms
        current_bpm = current_bpms.get(
            self.heart_rate_id, 60
        )  # Default to 60 BPM if not found
        if current_bpm > 0:
            # Convert BPM to milliseconds between beats (60000ms / BPM)
            self.time_between_frames_ms = (
                60000 / current_bpm / 2
            )  # Divide by 2 for heart animation (up/down)
        else:
            self.time_between_frames_ms = DEFAULT_TIME_BETWEEN_FRAMES_MS

        if self.time_since_last_update > self.time_between_frames_ms:
            self.time_since_last_update = 0

            self.up = not self.up
            self.image = self.small_heart_image if self.up else self.med_heart_image

        window.blit(self.image, (self.x, self.y - 8))
        self.display_number(
            window,
            (
                current_bpms[self.heart_rate_id]
                if self.heart_rate_id in current_bpms
                else 0
            ),
        )

        self.time_since_last_update += clock.get_time()

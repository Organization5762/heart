import time

from dataclasses import dataclass
from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
from pygame import font, Surface, time
from heart.peripheral.manager import PeripheralManager
from heart.peripheral.heart_rates import current_bpms


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0


WINDOW_SIZE = 5  # seconds


class MetadataScreen(BaseRenderer):
    def __init__(self, x, y, color, heart_rate_id) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.current_frame = 0
        self.color = color
        self.small_heart_image = Loader.load(
            Loader._resolve_path(f"hearts/{self.color}/small.png")
        )
        self.med_heart_image = Loader.load(
            Loader._resolve_path(f"hearts/{self.color}/med.png")
        )
        self.big_heart_image = Loader.load(
            Loader._resolve_path(f"hearts/{self.color}/big.png")
        )
        self.image = self.small_heart_image

        self.time_since_last_update = None
        self.time_between_frames_ms = 400
        self.time_since_last_update = 0

        self.heart_rate_id = heart_rate_id
        self.up = True

        print(current_bpms)

        self.x = x
        self.y = y

    def display_number(self, window, number):
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + 24, self.y + 25))
        window.blit(text, text_rect)

    def process(
        self,
        window: Surface,
        clock: time.Clock,
        peripheral_manager: PeripheralManager,
    ) -> None:
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

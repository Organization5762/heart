import time
from collections import deque
from dataclasses import dataclass

from pygame import font

from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
from heart.input.heart_rate import HeartRateSubscriber


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0


WINDOW_SIZE = 5  # seconds


class MetadataScreen(BaseRenderer):
    def __init__(self, x, y, color) -> None:
        super().__init__()
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
        self.time_between_frames_ms = 200
        self.time_since_last_beat = 0
        self.time_since_last_update = 0

        self.heart_rate = 0
        self.heart_rate_data = deque()

        self.up = True

        self.x = x
        self.y = y

    def update_heart_rate(self):
        self.heart_rate = HeartRateSubscriber.get().get_heart_rate()[65535]
        if self.heart_rate != 0:
            pass
            # self.time_between_frames_ms = (self.heart_rate / 60) * 1000
        else:
            self.time_between_frames_ms = float("inf")

    def display_number(self, window, number):
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + 24, self.y + 25))
        window.blit(text, text_rect)

    def process(self, window, clock) -> None:
        if self.heart_rate > 0:
            ms_to_wait_between = (60 / self.heart_rate) * 1000
            if self.time_since_last_beat > ms_to_wait_between:
                self.time_since_last_beat = 0

                self.up = not self.up
                self.image = self.small_heart_image if self.up else self.med_heart_image

        if self.time_since_last_update > self.time_between_frames_ms:
            self.time_since_last_update = 0
            self.update_heart_rate()

        window.blit(self.image, (self.x, self.y - 8))
        self.display_number(window, self.heart_rate)

        current_time = clock.get_time()
        self.time_since_last_beat += current_time
        self.time_since_last_update += current_time

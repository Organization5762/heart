import time

from dataclasses import dataclass
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer
from pygame import font
from collections import deque


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

        self.heart_rate = 0
        self.heart_rate_data = deque()

        self.up = True

        self.x = x
        self.y = y

    def add_data(self, new_data):
        self.heart_rate_data.append(
            (new_data.beat_time, new_data.beat_count, time.time())
        )

    def update_heart_rate(self):
        # Remove old data outside the window size
        while (
            self.heart_rate_data
            and (time.time() - self.heart_rate_data[0][2]) > WINDOW_SIZE
        ):
            self.heart_rate_data.popleft()

        # Compute heart rate if there are at least two points to calculate the difference
        if len(self.heart_rate_data) > 1:
            first_time = self.heart_rate_data[0][0]
            last_time = self.heart_rate_data[-1][0]
            first_heart_beat = self.heart_rate_data[0][1]
            last_heart_beat = self.heart_rate_data[-1][1]

            # The beat time is only from 0 to 64 and restarting at 0 after that
            # So if the last time is inferior to the first_time this means we need to add 64 to it
            if first_time > last_time:
                last_time += 64

            if first_heart_beat > last_heart_beat:
                last_heart_beat += 255

            if first_time == last_time or first_heart_beat == last_heart_beat:
                return

            time_diff = last_time - first_time
            beat_diff = last_heart_beat - first_heart_beat
            self.heart_rate = round(
                (beat_diff / time_diff) * 60
            )  # convert to beats per minute
            self.time_between_frames_ms = (self.heart_rate / 60) * 1000
            print(f"New heart rate {self.heart_rate}")
        else:
            self.heart_rate = 0
            self.time_between_frames_ms = float("inf")

    def display_number(self, window, number):
        my_font = font.Font(Loader._resolve_path("Grand9K Pixel.ttf"), 8)
        text = my_font.render(str(number).zfill(3), True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.x + 24, self.y + 25))
        window.blit(text, text_rect)

    def process(self, window, clock) -> None:
        if self.time_since_last_update > self.time_between_frames_ms:
            self.time_since_last_update = 0

            self.up = not self.up
            self.image = self.small_heart_image if self.up else self.med_heart_image

            self.update_heart_rate()

        window.blit(self.image, (self.x, self.y - 8))
        self.display_number(window, self.heart_rate)

        self.time_since_last_update += clock.get_time()

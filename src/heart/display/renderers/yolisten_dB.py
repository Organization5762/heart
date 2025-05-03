import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager
import requests
import threading
import time

PHYPOX_URL = "http://192.168.1.50/get?dB"

def poll_phyphox_background():
    while True:
        try:
            resp = requests.get(PHYPOX_URL, timeout=1)
            data = resp.json()
            return data['buffer']['dB']['buffer'][-1]
        except Exception:
            return 50.0
        time.sleep(0.05)

class YoListenDBRenderer(BaseRenderer):
    def __init__(self, color: Color = Color(255, 0, 0)) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.color = color
        self.words = ["YO", "LISTEN", "Y'HEAR", "THAT"]
        self.screen_count = 4
        self.ascii_art = {
            "YO": [
                "█  █ █▀▀█",
                " ██  █  █",
                " █▀  ███▀"
            ],
            "LISTEN": [
                "█     ▀█▀▀ █▀▀▀ █▀█▀ █▀▀▀ █  ██",
                "█      █   ▀▀██   █  █▀▀  █▀ ██",
                "█▀▀▀  ███▀ ▀███   █  ███▀ █ ▀██"
            ],
            "Y'HEAR": [
                [
                    "█  █ █▀▀█ █  █",
                    " ██  █  █ █  █",
                    " █▀  ███▀ ███▀"
                ],
                [
                    "█  █ █▀▀▀  █▀█ █▀▀█",
                    "█▀▀█ █▀▀  █▀ █ ██▀▀",
                    "█  █ ███▀ █▀▀█ █ ▀█"
                ]
            ],
            "THAT": [
                "█▀█▀ █  █  █▀█ █▀█▀",
                "  █  █▀▀█ █▀ █   █ ",
                "  █  █  █ █▀▀█   █ "
            ]
        }
        self.base_font_size = 2  # Base font size that will be scaled with dB
        self.max_font_size = 12  # Increased for more visible pulsing
        self.min_font_size = 2   # Minimum font size to maintain readability
        self.initialized = False
        self.ascii_font_sizes = {}  # Will be dynamically updated based on dB
        self.db_level = 50.0  # Default dB level
        self.db_thread = threading.Thread(target=self._update_db_background, daemon=True)
        self.db_thread.start()

    def _initialize(self) -> None:
        self.initialized = True

    def _update_db_background(self):
        while True:
            try:
                resp = requests.get(PHYPOX_URL, timeout=1)
                data = resp.json()
                new_db = abs(data['buffer']['dB']['buffer'][-1])
                self.db_level = 0.7 * self.db_level + 0.3 * new_db  # exponential smoothing
            except Exception as e:
                print(f"Error updating db level: {e}")
                #     self.db_level = 50.0
                pass

            time.sleep(0.05)

    def _draw_ascii_art(self, word: str, y_offset: int, screen_surface: pygame.Surface, font_size: int) -> None:
        ascii_font = pygame.font.SysFont("Courier New", font_size)
        if word == "Y'HEAR":
            blocks = self.ascii_art[word]
            spacing = 1
            line_idx = 0
            for block_i, block in enumerate(blocks):
                for line in block:
                    text_surface = ascii_font.render(line, True, self.color._as_tuple())
                    text_width, _ = text_surface.get_size()
                    x_centered = (screen_surface.get_width() - text_width) // 2
                    screen_surface.blit(text_surface, (x_centered, y_offset + line_idx * (font_size + 1)))
                    line_idx += 1
                if block_i == 0:
                    line_idx += spacing
        else:
            for j, line in enumerate(self.ascii_art[word]):
                text_surface = ascii_font.render(line, True, self.color._as_tuple())
                text_width, _ = text_surface.get_size()
                x_centered = (screen_surface.get_width() - text_width) // 2
                screen_surface.blit(text_surface, (x_centered, y_offset + j * (font_size + 1)))

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.initialized:
            self._initialize()
        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count
        window.fill((0, 0, 0))
        words_to_show = self.words
        # --- Map dB to font size ---
        min_db, max_db = 40, 80
        min_font, max_font = self.min_font_size, self.max_font_size
        db = self.db_level
        font_size = int(min_font + (max_font - min_font) * ((db - min_db) / (max_db - min_db)))
        # print(f"font_size: {font_size}")
        print(f"db: {db}")
        font_size = max(min_font, min(max_font, font_size))
        for i, word in enumerate(words_to_show):
            x_offset = i * screen_width
            if word == "Y'HEAR":
                total_lines = len(self.ascii_art[word][0]) + len(self.ascii_art[word][1]) + 1
            else:
                total_lines = len(self.ascii_art[word])
            y_offset = (window_height - (total_lines * (font_size + 1))) // 2
            screen_surface = window.subsurface(pygame.Rect(x_offset, 0, screen_width, window_height))
            self._draw_ascii_art(word, y_offset, screen_surface, font_size) 
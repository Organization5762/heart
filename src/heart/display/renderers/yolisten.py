import pygame
import requests
import time
import threading
import random

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager

PHYPOX_URL = "http://192.168.1.50/get?accY&accX&accZ&dB"

class YoListenRenderer(BaseRenderer):
    def __init__(self, color: Color = Color(255, 0, 0)) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.base_color = color  # Store the base color
        self.color = color  # This will be the flickering color
        self.words = ["YO", "LISTEN", "Y'HEAR", "THAT"]
        self.screen_count = 4
        self.flicker_intensity = 0.4
        self.flicker_speed = 0.04  # How often to update the flicker (in seconds)
        self.last_flicker_update = 0
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
        self.last_flash_time = 0
        self.flash_delay = 100
        self.ascii_font_sizes = {}
        self.initialized = False
        # --- Phyphox phone accel ---
        self.phyphox_accel_x = 0.0
        self.phyphox_accel_y = 0.0
        self.phyphox_accel_z = 0.0
        self.use_phyphox = True  # Set to True to use phone input
        if self.use_phyphox:
            threading.Thread(target=self._poll_phyphox_background, daemon=True).start()
        # --- Simulated accel for test mode ---
        self.sim_accel_x = 0.0
        self.sim_accel_y = 0.0
        self.sim_accel_step = 0.1
        self.test_mode = False
        self.phyphox_db = 50.0

    def _initialize(self) -> None:
        for word in self.words:
            self.ascii_font_sizes[word] = self._calculate_optimal_ascii_font_size(word)
        self.initialized = True

    def _calculate_optimal_ascii_font_size(self, word: str) -> int:
        art = self.ascii_art[word]
        # For Y'HEAR, flatten the two blocks
        if word == "Y'HEAR":
            art = art[0] + art[1]
        font_size = 4
        font = pygame.font.SysFont("Courier New", font_size)
        longest_line = max(len(line) for line in art)
        text_width, _ = font.size("█" * longest_line)
        while text_width <= 60:
            font_size += 1
            font = pygame.font.SysFont("Courier New", font_size)
            text_width, _ = font.size("█" * longest_line)
        return max(4, font_size - 1)

    def _draw_ascii_art(self, word: str, y_offset: int, screen_surface: pygame.Surface) -> None:
        ascii_font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
        if word == "Y'HEAR":
            blocks = self.ascii_art[word]
            spacing = 1  # integer spacing for pygame
            line_idx = 0
            for block_i, block in enumerate(blocks):
                for line in block:
                    text_surface = ascii_font.render(line, True, self.color._as_tuple())
                    text_width, _ = text_surface.get_size()
                    x_centered = (screen_surface.get_width() - text_width) // 2
                    screen_surface.blit(text_surface, (x_centered, y_offset + line_idx * (self.ascii_font_sizes[word] + 1)))
                    line_idx += 1
                if block_i == 0:
                    line_idx += spacing  # add spacing only between blocks
        else:
            for j, line in enumerate(self.ascii_art[word]):
                text_surface = ascii_font.render(line, True, self.color._as_tuple())
                text_width, _ = text_surface.get_size()
                x_centered = (screen_surface.get_width() - text_width) // 2
                screen_surface.blit(text_surface, (x_centered, y_offset + j * (self.ascii_font_sizes[word] + 1)))

    def _poll_phyphox_background(self):
        while True:
            try:
                resp = requests.get(PHYPOX_URL, timeout=1)
                data = resp.json()
                self.phyphox_accel_x = data['buffer']['accX']['buffer'][-1]
                self.phyphox_accel_y = data['buffer']['accY']['buffer'][-1]
                self.phyphox_accel_z = data['buffer']['accZ']['buffer'][-1]
                self.phyphox_db = data['buffer']['dB']['buffer'][-1]
            except Exception:
                pass
            time.sleep(0.05)

    def _update_flicker(self, current_time: float) -> None:
        if current_time - self.last_flicker_update >= self.flicker_speed:
            # Generate a random brightness factor between (1 - intensity) and (1 + intensity)
            brightness_factor = 1 + random.uniform(-self.flicker_intensity, self.flicker_intensity)
            # Apply the brightness factor to each color channel
            r = min(255, max(0, int(self.base_color.r * brightness_factor)))
            g = min(255, max(0, int(self.base_color.g * brightness_factor)))
            b = min(255, max(0, int(self.base_color.b * brightness_factor)))
            self.color = Color(r, g, b)
            self.last_flicker_update = current_time

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:

        if not self.initialized:
            self._initialize()
        
        # Update the flickering effect
        current_time = time.time()
        self._update_flicker(current_time)
        
        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count
        window.fill((0, 0, 0))
        # --- ACCELEROMETER-BASED MOVEMENT ---
        if self.use_phyphox:
            accel_x = self.phyphox_accel_x
            accel_y = self.phyphox_accel_y
        else:
            try:
                accel = peripheral_manager.get_accelerometer().get_acceleration()
                accel_x = accel.x
                accel_y = accel.y
            except Exception:
                self.test_mode = True
                accel_x = self.sim_accel_x
                accel_y = self.sim_accel_y

        x_offset_accel = int(accel_x * 10)
        y_offset_accel = int(accel_y * 10)
        max_x = screen_width // 2 - 10
        min_x = -max_x
        max_y = window_height // 2 - 10
        min_y = -max_y
        x_offset_accel = max(min_x, min(max_x, x_offset_accel))
        y_offset_accel = max(min_y, min(max_y, y_offset_accel))

        # No flash effect - always show
        should_show = True

        if should_show:
            words_to_show = self.words
            for i, word in enumerate(words_to_show):
                x_offset = i * screen_width
                if word == "Y'HEAR":
                    total_lines = len(self.ascii_art[word][0]) + len(self.ascii_art[word][1]) + 1  # 1 for spacing
                else:
                    total_lines = len(self.ascii_art[word])
                y_offset = (window_height - (total_lines * (self.ascii_font_sizes[word] + 1))) // 2
                y_offset += y_offset_accel
                screen_surface = window.subsurface(pygame.Rect(x_offset, 0, screen_width, window_height))
                self._draw_ascii_art_with_x_offset(word, y_offset, screen_surface, x_offset_accel)

    def _draw_ascii_art_with_x_offset(self, word: str, y_offset: int, screen_surface: pygame.Surface, x_offset_accel: int) -> None:
        ascii_font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
        if word == "Y'HEAR":
            blocks = self.ascii_art[word]
            spacing = 1
            line_idx = 0
            for block_i, block in enumerate(blocks):
                for line in block:
                    text_surface = ascii_font.render(line, True, self.color._as_tuple())
                    text_width, _ = text_surface.get_size()
                    x_centered = (screen_surface.get_width() - text_width) // 2 + x_offset_accel
                    screen_surface.blit(text_surface, (x_centered, y_offset + line_idx * (self.ascii_font_sizes[word] + 1)))
                    line_idx += 1
                if block_i == 0:
                    line_idx += spacing
        else:
            for j, line in enumerate(self.ascii_art[word]):
                text_surface = ascii_font.render(line, True, self.color._as_tuple())
                text_width, _ = text_surface.get_size()
                x_centered = (screen_surface.get_width() - text_width) // 2 + x_offset_accel
                screen_surface.blit(text_surface, (x_centered, y_offset + j * (self.ascii_font_sizes[word] + 1)))

def poll_phyphox():
    while True:
        try:
            resp = requests.get(PHYPOX_URL, timeout=1)
            data = resp.json()
            # The structure may vary, but typically:
            x = data['buffer']['acceleration']['x'][-1]
            y = data['buffer']['acceleration']['y'][-1]
            z = data['buffer']['acceleration']['z'][-1]
            print(f"x={x}, y={y}, z={z}")
        except Exception as e:
            print("Error:", e)
        time.sleep(0.1) 

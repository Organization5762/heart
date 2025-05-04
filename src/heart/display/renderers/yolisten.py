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
        self.scroll_speed = 0.5  # pixels per frame
        self._base_scroll_speed = 0.5  # Store the base scroll speed
        self._should_calibrate = True
        self._scroll_speed_offset = 0
        self.word_positions = [0]  # Single position for all words
        self.word_widths = {}  # Store width of each word
        self.word_spacing = 0  # Space between words
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
            # Calculate and store the width of each word
            font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
            if word == "Y'HEAR":
                # For Y'HEAR, calculate the width of both blocks and add them together
                block1_width, _ = font.size(self.ascii_art[word][0][0])
                block2_width, _ = font.size(self.ascii_art[word][1][0])
                # Add a small spacing between blocks
                self.word_widths[word] = max(block1_width, block2_width) + 5
            else:
                text_width, _ = font.size(self.ascii_art[word][0])
                self.word_widths[word] = text_width
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

    def _calibrate_scroll_speed(self, peripheral_manager: PeripheralManager):
        self._scroll_speed_offset = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        self._should_calibrate = False

    def _scroll_speed_scale_factor(self, peripheral_manager: PeripheralManager) -> float:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        return 1.0 + (current_value - self._scroll_speed_offset) / 20.0

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.initialized:
            self._initialize()
        if self._should_calibrate:
            self._calibrate_scroll_speed(peripheral_manager)
        self.scroll_speed = self._base_scroll_speed * self._scroll_speed_scale_factor(peripheral_manager)
        # Update the flickering effect
        current_time = time.time()
        self._update_flicker(current_time)
        
        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count
        window.fill((0, 0, 0))

        # Update the single position for all words
        self.word_positions[0] -= self.scroll_speed
        # Reset position when words move completely off screen
        if self.word_positions[0] < -window_width:
            self.word_positions[0] = 0

        # Draw all words at their relative positions, including duplicates for looping
        for i, word in enumerate(self.words):
            # Calculate the word's x position relative to the entire display
            word_x = self.word_positions[0] + (i * (screen_width + self.word_spacing))
            
            # Draw the word and its duplicate for looping
            for offset in [0, window_width]:
                current_x = word_x + offset
                
                # Only draw if the word is visible on any screen
                if current_x < window_width and current_x > -self.word_widths[word]:
                    # Calculate which screen(s) the word is on
                    start_screen = max(0, int(current_x // screen_width))
                    end_screen = min(self.screen_count, int((current_x + self.word_widths[word]) // screen_width + 1))
                    
                    for screen in range(start_screen, end_screen):
                        screen_x = screen * screen_width
                        screen_surface = window.subsurface(pygame.Rect(screen_x, 0, screen_width, window_height))
                        
                        # Calculate y offset for vertical centering
                        if word == "Y'HEAR":
                            total_lines = len(self.ascii_art[word][0]) + len(self.ascii_art[word][1]) + 1
                        else:
                            total_lines = len(self.ascii_art[word])
                        y_offset = (window_height - (total_lines * (self.ascii_font_sizes[word] + 1))) // 2
                        
                        # Draw the word with its current x position relative to the screen
                        self._draw_ascii_art_with_x_offset(word, y_offset, screen_surface, int(current_x - screen_x))

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
                    line_idx += spacing  # add spacing only between blocks
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
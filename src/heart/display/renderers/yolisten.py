import random
import threading
import time
from dataclasses import dataclass

import pygame
import requests

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState

# TODO: Move to peripheral
PHYPOX_URL = "http://192.168.1.50/get?accY&accX&accZ&dB"


@dataclass
class YoListenState:
    switch_state: SwitchState | None
    color: Color
    last_flicker_update: float = 0.0
    should_calibrate: bool = True
    scroll_speed_offset: float = 0.0
    word_position: float = 0.0


class YoListenRenderer(AtomicBaseRenderer[YoListenState]):
    def __init__(self, color: Color = Color(255, 0, 0)) -> None:
        self.base_color = color  # Store the base color
        self.words = ["YO", "LISTEN", "Y'HEAR", "THAT"]
        self.screen_count = 4
        self.flicker_intensity = 0.4
        self.flicker_speed = 0.04  # How often to update the flicker (in seconds)
        self._base_scroll_speed = 0.5  # Store the base scroll speed
        self.word_widths = {}  # Store width of each word
        self.word_spacing = 0  # Space between words
        self.ascii_art = {
            "YO": ["█  █ █▀▀█", " ██  █  █", " █▀  ███▀"],
            "LISTEN": [
                "█     ▀█▀▀ █▀▀▀ █▀█▀ █▀▀▀ █  ██",
                "█      █   ▀▀██   █  █▀▀  █▀ ██",
                "█▀▀▀  ███▀ ▀███   █  ███▀ █ ▀██",
            ],
            "Y'HEAR": [
                ["█  █ █▀▀█ █  █", " ██  █  █ █  █", " █▀  ███▀ ███▀"],
                ["█  █ █▀▀▀  █▀█ █▀▀█", "█▀▀█ █▀▀  █▀ █ ██▀▀", "█  █ ███▀ █▀▀█ █ ▀█"],
            ],
            "THAT": [
                "█▀█▀ █  █  █▀█ █▀█▀",
                "  █  █▀▀█ █▀ █   █ ",
                "  █  █  █ █▀▀█   █ ",
            ],
        }
        self.flash_delay = 100
        self.ascii_font_sizes = {}
        # --- Phyphox phone accel ---
        self.phyphox_accel_x = 0.0
        self.phyphox_accel_y = 0.0
        self.phyphox_accel_z = 0.0
        # We won't have phone input for now as we don't have internet access
        # TODO: Do we want to just hook this into the Accelerometer?
        self.use_phyphox = False  # Set to True to use phone input
        if self.use_phyphox:
            threading.Thread(target=self._poll_phyphox_background, daemon=True).start()
        # --- Simulated accel for test mode ---
        self.sim_accel_x = 0.0
        self.sim_accel_y = 0.0
        self.sim_accel_step = 0.1
        self.test_mode = False
        self.phyphox_db = 50.0
        AtomicBaseRenderer.__init__(self)

        self.device_display_mode = DeviceDisplayMode.FULL

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

    def _draw_ascii_art(
        self, word: str, y_offset: int, screen_surface: pygame.Surface
    ) -> None:
        ascii_font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
        color = self.state.color
        if word == "Y'HEAR":
            blocks = self.ascii_art[word]
            spacing = 1  # integer spacing for pygame
            line_idx = 0
            for block_i, block in enumerate(blocks):
                for line in block:
                    text_surface = ascii_font.render(line, True, color._as_tuple())
                    text_width, _ = text_surface.get_size()
                    x_centered = (screen_surface.get_width() - text_width) // 2
                    screen_surface.blit(
                        text_surface,
                        (
                            x_centered,
                            y_offset + line_idx * (self.ascii_font_sizes[word] + 1),
                        ),
                    )
                    line_idx += 1
                if block_i == 0:
                    line_idx += spacing  # add spacing only between blocks
        else:
            for j, line in enumerate(self.ascii_art[word]):
                text_surface = ascii_font.render(line, True, color._as_tuple())
                text_width, _ = text_surface.get_size()
                x_centered = (screen_surface.get_width() - text_width) // 2
                screen_surface.blit(
                    text_surface,
                    (x_centered, y_offset + j * (self.ascii_font_sizes[word] + 1)),
                )

    def _poll_phyphox_background(self):
        while True:
            try:
                resp = requests.get(PHYPOX_URL, timeout=1)
                data = resp.json()
                self.phyphox_accel_x = data["buffer"]["accX"]["buffer"][-1]
                self.phyphox_accel_y = data["buffer"]["accY"]["buffer"][-1]
                self.phyphox_accel_z = data["buffer"]["accZ"]["buffer"][-1]
                self.phyphox_db = data["buffer"]["dB"]["buffer"][-1]
            except Exception:
                pass
            time.sleep(0.05)

    def _update_flicker(self, current_time: float, state: YoListenState) -> YoListenState:
        if current_time - state.last_flicker_update >= self.flicker_speed:
            # Generate a random brightness factor between (1 - intensity) and (1 + intensity)
            brightness_factor = 1 + random.uniform(
                -self.flicker_intensity, self.flicker_intensity
            )
            # Apply the brightness factor to each color channel
            r = min(255, max(0, int(self.base_color.r * brightness_factor)))
            g = min(255, max(0, int(self.base_color.g * brightness_factor)))
            b = min(255, max(0, int(self.base_color.b * brightness_factor)))
            self.update_state(
                color=Color(r, g, b),
                last_flicker_update=current_time,
            )
            return self.state
        return state

    # TODO: We could just narrow the state instead of storing two redundant values
    def _calibrate_scroll_speed(self, state: YoListenState) -> YoListenState:
        rotation = 0
        if self.state.switch_state:
            rotation = self.state.switch_state.rotation_since_last_button_press
        self.update_state(
            scroll_speed_offset=rotation,
            should_calibrate=False,
        )
        return self.state

    def _scroll_speed_scale_factor(self, state: YoListenState) -> float:
        current_value = 0
        if self.state.switch_state:
            current_value = self.state.switch_state.rotation_since_last_button_press
        return 1.0 + (current_value - state.scroll_speed_offset) / 20.0

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        if state.should_calibrate:
            state = self._calibrate_scroll_speed(state)
        scroll_speed = self._base_scroll_speed * self._scroll_speed_scale_factor(state)

        # Update the flickering effect
        current_time = time.time()
        state = self._update_flicker(current_time, state)

        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count
        window.fill((0, 0, 0))

        # Update the single position for all words
        word_position = state.word_position - scroll_speed
        # Reset position when words move completely off screen
        if word_position < -window_width:
            word_position = 0

        if word_position != state.word_position:
            self.update_state(word_position=word_position)
            state = self.state

        color = state.color
        word_position = state.word_position

        # Draw all words at their relative positions, including duplicates for looping
        for i, word in enumerate(self.words):
            # Calculate the word's x position relative to the entire display
            word_x = word_position + (i * (screen_width + self.word_spacing))

            # Draw the word and its duplicate for looping
            for offset in [0, window_width]:
                current_x = word_x + offset

                # Only draw if the word is visible on any screen
                if current_x < window_width and current_x > -self.word_widths[word]:
                    # Calculate which screen(s) the word is on
                    start_screen = max(0, int(current_x // screen_width))
                    end_screen = min(
                        self.screen_count,
                        int((current_x + self.word_widths[word]) // screen_width + 1),
                    )

                    for screen in range(start_screen, end_screen):
                        screen_x = screen * screen_width
                        screen_surface = window.subsurface(
                            pygame.Rect(screen_x, 0, screen_width, window_height)
                        )

                        # Calculate y offset for vertical centering
                        if word == "Y'HEAR":
                            total_lines = (
                                len(self.ascii_art[word][0])
                                + len(self.ascii_art[word][1])
                                + 1
                            )
                        else:
                            total_lines = len(self.ascii_art[word])
                        y_offset = (
                            window_height
                            - (total_lines * (self.ascii_font_sizes[word] + 1))
                        ) // 2

                        # Draw the word with its current x position relative to the screen
                        self._draw_ascii_art_with_x_offset(
                            word,
                            y_offset,
                            screen_surface,
                            int(current_x - screen_x),
                            color,
                        )

    def _draw_ascii_art_with_x_offset(
        self,
        word: str,
        y_offset: int,
        screen_surface: pygame.Surface,
        x_offset_accel: int,
        color: Color,
    ) -> None:
        ascii_font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
        if word == "Y'HEAR":
            blocks = self.ascii_art[word]
            spacing = 1
            line_idx = 0
            for block_i, block in enumerate(blocks):
                for line in block:
                    text_surface = ascii_font.render(line, True, color._as_tuple())
                    text_width, _ = text_surface.get_size()
                    x_centered = (
                        screen_surface.get_width() - text_width
                    ) // 2 + x_offset_accel
                    screen_surface.blit(
                        text_surface,
                        (
                            x_centered,
                            y_offset + line_idx * (self.ascii_font_sizes[word] + 1),
                        ),
                    )
                    line_idx += 1
                if block_i == 0:
                    line_idx += spacing  # add spacing only between blocks
        else:
            for j, line in enumerate(self.ascii_art[word]):
                text_surface = ascii_font.render(line, True, color._as_tuple())
                text_width, _ = text_surface.get_size()
                x_centered = (
                    screen_surface.get_width() - text_width
                ) // 2 + x_offset_accel
                screen_surface.blit(
                    text_surface,
                    (x_centered, y_offset + j * (self.ascii_font_sizes[word] + 1)),
                )

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
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

        def new_switch_state(v):
            self.state.switch_state = v
        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next = new_switch_state,
            on_error = lambda e: print("Error Occurred: {0}".format(e)),
        )
        return YoListenState(color=self.base_color, switch_state=None)


def poll_phyphox():
    while True:
        try:
            resp = requests.get(PHYPOX_URL, timeout=1)
            data = resp.json()
            # The structure may vary, but typically:
            x = data["buffer"]["acceleration"]["x"][-1]
            y = data["buffer"]["acceleration"]["y"][-1]
            z = data["buffer"]["acceleration"]["z"][-1]
            print(f"x={x}, y={y}, z={z}")
        except Exception as e:
            print("Error:", e)
        time.sleep(0.1)

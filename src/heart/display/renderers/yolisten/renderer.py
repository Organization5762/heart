import logging
import random
import threading
import time

import pygame
import requests

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.yolisten.provider import YoListenStateProvider
from heart.display.renderers.yolisten.state import YoListenState
from heart.peripheral.core.manager import PeripheralManager

PHYPOX_URL = "http://192.168.1.50/get?accY&accX&accZ&dB"
logger = logging.getLogger(__name__)


class YoListenRenderer(AtomicBaseRenderer[YoListenState]):
    def __init__(self, color: Color = Color(255, 0, 0), provider: YoListenStateProvider | None = None) -> None:
        self.base_color = color
        self.words = ["YO", "LISTEN", "Y'HEAR", "THAT"]
        self.screen_count = 4
        self.flicker_intensity = 0.4
        self.flicker_speed = 0.04
        self._base_scroll_speed = 0.5
        self.word_widths: dict[str, int] = {}
        self.word_spacing = 0
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
        self.ascii_font_sizes: dict[str, int] = {}
        self.phyphox_accel_x = 0.0
        self.phyphox_accel_y = 0.0
        self.phyphox_accel_z = 0.0
        self.use_phyphox = False
        if self.use_phyphox:
            threading.Thread(target=self._poll_phyphox_background, daemon=True).start()
        self.sim_accel_x = 0.0
        self.sim_accel_y = 0.0
        self.sim_accel_step = 0.1
        self.test_mode = False
        self.phyphox_db = 50.0
        self.provider = provider or YoListenStateProvider(color)
        AtomicBaseRenderer.__init__(self)

        self.device_display_mode = DeviceDisplayMode.FULL

    def _calculate_optimal_ascii_font_size(self, word: str) -> int:
        art = self.ascii_art[word]
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
            spacing = 1
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
                    line_idx += spacing
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
                logger.exception("Failed to poll phyphox data")
            time.sleep(0.05)

    def _update_flicker(self, current_time: float, state: YoListenState) -> YoListenState:
        if current_time - state.last_flicker_update >= self.flicker_speed:
            brightness_factor = 1 + random.uniform(
                -self.flicker_intensity, self.flicker_intensity
            )
            r = min(255, max(0, int(self.base_color.r * brightness_factor)))
            g = min(255, max(0, int(self.base_color.g * brightness_factor)))
            b = min(255, max(0, int(self.base_color.b * brightness_factor)))
            self.update_state(
                color=Color(r, g, b),
                last_flicker_update=current_time,
            )
            return self.state
        return state

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

        current_time = time.time()
        state = self._update_flicker(current_time, state)

        window_width, window_height = window.get_size()
        screen_width = window_width // self.screen_count
        window.fill((0, 0, 0))

        word_position = state.word_position - scroll_speed
        if word_position < -window_width:
            word_position = 0

        if word_position != state.word_position:
            self.update_state(word_position=word_position)
            state = self.state

        color = state.color
        word_position = state.word_position

        for i, word in enumerate(self.words):
            word_x = word_position + (i * (screen_width + self.word_spacing))
            for offset in [0, window_width]:
                current_x = word_x + offset
                if current_x < window_width and current_x > -self.word_widths[word]:
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
                    line_idx += spacing
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
        orientation: Orientation,
    ) -> YoListenState:
        for word in self.words:
            self.ascii_font_sizes[word] = self._calculate_optimal_ascii_font_size(word)
            font = pygame.font.SysFont("Courier New", self.ascii_font_sizes[word])
            if word == "Y'HEAR":
                block1_width, _ = font.size(self.ascii_art[word][0][0])
                block2_width, _ = font.size(self.ascii_art[word][1][0])
                self.word_widths[word] = max(block1_width, block2_width) + 5
            else:
                text_width, _ = font.size(self.ascii_art[word][0])
                self.word_widths[word] = text_width

        return self.provider.create_initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
            on_switch_state=lambda value: self.update_state(switch_state=value),
        )


def poll_phyphox():
    while True:
        try:
            resp = requests.get(PHYPOX_URL, timeout=1)
            data = resp.json()
            x = data["buffer"]["acceleration"]["x"][-1]
            y = data["buffer"]["acceleration"]["y"][-1]
            z = data["buffer"]["acceleration"]["z"][-1]
            print(f"x={x}, y={y}, z={z}")
        except Exception as exc:
            logger.error("Error: %s", exc)
        time.sleep(0.1)

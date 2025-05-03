import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager


class YoListenRenderer(BaseRenderer):
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
        self.last_flash_time = 0
        self.flash_delay = 100
        self.ascii_font_sizes = {}
        self.initialized = False

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
        rotation = peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        base_words = min(max(0, rotation // 5), len(self.words))
        extra_rotation = max(0, rotation - (len(self.words) * 5))
        current_time = pygame.time.get_ticks()
        should_show = True
        if base_words == len(self.words) and extra_rotation > 0:
            flash_cycle = (current_time - self.last_flash_time) // self.flash_delay
            should_show = flash_cycle % 2 == 0
            if (current_time - self.last_flash_time) >= self.flash_delay:
                self.last_flash_time = current_time
        if should_show:
            words_to_show = self.words[:base_words]
            for i, word in enumerate(words_to_show):
                x_offset = i * screen_width
                if word == "Y'HEAR":
                    total_lines = len(self.ascii_art[word][0]) + len(self.ascii_art[word][1]) + 1  # 1 for spacing
                else:
                    total_lines = len(self.ascii_art[word])
                y_offset = (window_height - (total_lines * (self.ascii_font_sizes[word] + 1))) // 2
                screen_surface = window.subsurface(pygame.Rect(x_offset, 0, screen_width, window_height))
                self._draw_ascii_art(word, y_offset, screen_surface) 
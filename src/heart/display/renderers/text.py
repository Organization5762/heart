import json
from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.input.switch import SwitchSubscriber


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0


class TextRendering(BaseRenderer):
    def __init__(
        self,
        text: list[str],
        font: str,
        font_size: int,
        color: Color,
        x_location: int | None = None,
        y_location: int | None = None,
    ) -> None:
        super().__init__()
        self.color = color
        self.font_name = font
        self.font_size = font_size
        self.x_location = x_location
        self.y_location = y_location
        self.initialized = False
        self.text = text

        self.time_since_last_update = None

    def _initialize(self) -> None:
        self.font = pygame.font.SysFont(self.font_name, self.font_size)

        self.initialized = True

    def _current_text(self) -> str:
        current_value = SwitchSubscriber.get().get_rotation_since_last_button_press()
        current_text_idx = current_value % len(self.text)
        return self.text[current_text_idx]

    def process(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        if not self.initialized:
            self._initialize()

        current_text = self._current_text()

        lines = current_text.split("\n")
        total_text_height = len(lines) * self.font.get_linesize()
        window_width, window_height = window.get_size()

        x_offset = self.x_location
        y_offset = self.y_location

        if self.y_location is None:
            y_offset = (window_height - total_text_height) // 2

        for line in lines:
            text_surface = self.font.render(line, True, self.color._as_tuple())
            text_width, _ = text_surface.get_size()
            if self.x_location is None:
                x_offset = (window_width - text_width) // 2

            window.blit(text_surface, (x_offset, y_offset))
            y_offset += self.font.get_linesize()

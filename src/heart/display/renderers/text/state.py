from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import pygame

from heart.display.color import Color
from heart.peripheral.switch import SwitchState


@dataclass
class TextRenderingState:
    switch_state: SwitchState | None
    text: tuple[str, ...]
    font_name: str
    font_size: int
    color: Color
    x_location: int | None
    y_location: int | None

    @cached_property
    def font(self) -> pygame.font.Font:
        return pygame.font.SysFont(
            self.font_name,
            self.font_size,
        )

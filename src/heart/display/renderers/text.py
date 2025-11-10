from dataclasses import dataclass

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.internal import SwitchStateConsumer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class TextRenderingState:
    text: tuple[str, ...]
    font_name: str
    font_size: int
    color: Color
    x_location: int | None
    y_location: int | None
    font: pygame.font.Font | None = None


class TextRendering(
    SwitchStateConsumer, AtomicBaseRenderer[TextRenderingState]
):
    def __init__(
        self,
        text: list[str],
        font: str,
        font_size: int,
        color: Color,
        x_location: int | None = None,
        y_location: int | None = None,
    ) -> None:
        SwitchStateConsumer.__init__(self)
        self._initial_text = tuple(text)
        self._initial_font_name = font
        self._initial_font_size = font_size
        self._initial_color = color
        self._initial_x_location = x_location
        self._initial_y_location = y_location
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(self) -> TextRenderingState:
        return TextRenderingState(
            text=self._initial_text,
            font_name=self._initial_font_name,
            font_size=self._initial_font_size,
            color=self._initial_color,
            x_location=self._initial_x_location,
            y_location=self._initial_y_location,
            font=None,
        )

    @classmethod
    def default(cls, text: str):
        return cls(
            text=[text],
            font="Roboto",
            font_size=14,
            color=Color(255, 105, 180),
            x_location=None,
            y_location=None,
        )

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        font = pygame.font.SysFont(
            self.state.font_name, self.state.font_size
        )
        self.update_state(font=font)
        self.bind_switch(peripheral_manager)
        super().initialize(window, clock, peripheral_manager, orientation)

    def _current_text(self) -> str:
        state = self.get_switch_state()
        current_text_idx = state.rotation_since_last_button_press % len(
            self.state.text
        )
        return self.state.text[current_text_idx]


    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        current_text = self._current_text()

        lines = current_text.split("\n")
        font = self.state.font
        if font is None:
            return

        total_text_height = len(lines) * font.get_linesize()
        window_width, window_height = window.get_size()

        x_offset = self.state.x_location
        y_offset = self.state.y_location

        if self.state.y_location is None:
            y_offset = (window_height - total_text_height) // 2

        for line in lines:
            text_surface = font.render(line, True, self.state.color._as_tuple())
            text_width, _ = text_surface.get_size()
            if self.state.x_location is None:
                x_offset = (window_width - text_width) // 2

            window.blit(text_surface, (x_offset, y_offset))
            y_offset += font.get_linesize()

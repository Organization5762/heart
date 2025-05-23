import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


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
        self.text = text

        self.time_since_last_update = None

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
        self.font = pygame.font.SysFont(self.font_name, self.font_size)
        super().initialize(window, clock, peripheral_manager, orientation)

    def _current_text(self, peripheral_manager: PeripheralManager) -> str:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_button_press()
        )
        current_text_idx = current_value % len(self.text)
        return self.text[current_text_idx]

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        current_text = self._current_text(peripheral_manager=peripheral_manager)

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

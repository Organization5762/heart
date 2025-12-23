import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.text.provider import TextRenderingProvider
from heart.renderers.text.state import TextRenderingState


class TextRendering(StatefulBaseRenderer[TextRenderingState]):
    def __init__(
        self,
        text: list[str],
        font: str,
        font_size: int,
        color: Color,
        x_location: int | None = None,
        y_location: int | None = None,
    ) -> None:
        self._font: pygame.font.Font | None = None
        self._provider = TextRenderingProvider(
            text=text,
            font_name=font,
            font_size=font_size,
            color=color,
            x_location=x_location,
            y_location=y_location,
        )
        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> TextRenderingState:
        state = self._provider.build(
            peripheral_manager=peripheral_manager,
            orientation=orientation,
            window=window,
            clock=clock,
        )
        self._font = pygame.font.SysFont(
            state.font_name,
            state.font_size,
        )
        return state

    @classmethod
    def default(cls, text: str) -> "TextRendering":
        return cls(
            text=[text],
            font="Roboto",
            font_size=14,
            color=Color(255, 105, 180),
            x_location=None,
            y_location=None,
        )

    def _current_text(self) -> str:
        if not self.state.switch_state:
            state = 0
        else:
            state = self.state.switch_state.rotation_since_last_button_press

        current_text_idx = state % len(
            self.state.text
        )
        return self.state.text[current_text_idx]

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        current_text = self._current_text()

        lines = current_text.split("\n")
        font = self._font
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

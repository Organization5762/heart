from __future__ import annotations

from dataclasses import replace

from manyfold import Subscribable
from manyfold.architecture import PubSubObservable

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.renderers.text.state import TextRenderingState


class TextRenderingProvider(StateProvider[TextRenderingState]):
    def __init__(
        self,
        *,
        text: list[str],
        font_name: str,
        font_size: int,
        color: Color,
        x_location: int | None,
        y_location: int | None,
        line_spacing_px: int = 0,
    ) -> None:
        self._text = tuple(text)
        self._font_name = font_name
        self._font_size = font_size
        self._color = color
        self._x_location = x_location
        self._y_location = y_location
        self._line_spacing_px = line_spacing_px

    def states(
        self, peripheral_manager: PeripheralManager
    ) -> Subscribable[TextRenderingState]:
        initial_state = TextRenderingState(
            switch_state=None,
            text=self._text,
            font_name=self._font_name,
            font_size=self._font_size,
            color=self._color,
            x_location=self._x_location,
            y_location=self._y_location,
            line_spacing_px=self._line_spacing_px,
        )
        return PubSubObservable.merge(
            peripheral_manager.input_io.main_switch_stream().map(
                lambda switch_event: switch_event.state
            )
        ).state(
            initial_state,
            lambda state, switch_state: replace(state, switch_state=switch_state),
        )

    @classmethod
    def default(cls, text: str) -> "TextRenderingProvider":
        return cls(
            text=[text],
            font_name="Grand9K Pixel.ttf",
            font_size=14,
            color=Color(255, 105, 180),
            x_location=None,
            y_location=None,
            line_spacing_px=0,
        )

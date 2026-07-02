from __future__ import annotations

from dataclasses import replace

from manyfold.architecture import PubSubObservable

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.peripheral.switch import SwitchState
from heart.renderers.text.state import TextRenderingState


class TextRenderingProvider(ObservableProvider[TextRenderingState]):
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

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> Variable[TextRenderingState]:
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
            peripheral_manager.input_io.main_switch_stream().map(_switch_state)
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


def _switch_state(switch_event: object) -> SwitchState:
    state = getattr(switch_event, "state", switch_event)
    if not isinstance(state, SwitchState):
        raise TypeError("switch event must contain a SwitchState")
    return state

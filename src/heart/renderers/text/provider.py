from __future__ import annotations

from dataclasses import replace

import reactivex
from reactivex import operators as ops

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.text.state import TextRenderingState
from heart.utilities.reactivex_threads import pipe_in_background


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
    ) -> None:
        self._text = tuple(text)
        self._font_name = font_name
        self._font_size = font_size
        self._color = color
        self._x_location = x_location
        self._y_location = y_location

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[TextRenderingState]:
        initial_state = TextRenderingState(
            switch_state=None,
            text=self._text,
            font_name=self._font_name,
            font_size=self._font_size,
            color=self._color,
            x_location=self._x_location,
            y_location=self._y_location,
        )

        return pipe_in_background(
            peripheral_manager.get_main_switch_subscription(),
            ops.start_with(None),
            ops.scan(
                lambda state, switch_state: replace(
                    state, switch_state=switch_state
                ),
                seed=initial_state,
            ),
            ops.start_with(initial_state),
            ops.share(),
        )

    @classmethod
    def default(cls, text: str) -> "TextRenderingProvider":
        return cls(
            text=[text],
            font_name="Roboto",
            font_size=14,
            color=Color(255, 105, 180),
            x_location=None,
            y_location=None,
        )

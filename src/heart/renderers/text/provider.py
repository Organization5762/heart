from __future__ import annotations

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.text.state import TextRenderingState


class TextRenderingProvider:
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

    def build(
        self,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        window: pygame.Surface,
        clock: pygame.time.Clock,
    ) -> TextRenderingState:
        state = TextRenderingState(
            switch_state=None,
            text=self._text,
            font_name=self._font_name,
            font_size=self._font_size,
            color=self._color,
            x_location=self._x_location,
            y_location=self._y_location,
        )

        def new_switch_state(value):
            state.switch_state = value

        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=new_switch_state,
            on_error=lambda e: print("Error Occurred: {0}".format(e)),
        )

        return state

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

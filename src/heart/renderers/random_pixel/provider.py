from __future__ import annotations

from dataclasses import replace

import reactivex
from reactivex.subject import BehaviorSubject

from heart.display.color import Color
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.random_pixel.state import RandomPixelState


class RandomPixelStateProvider(ObservableProvider[RandomPixelState]):
    def __init__(self, initial_color: Color | None = None) -> None:
        self._state = BehaviorSubject(RandomPixelState(color=initial_color))

    def observable(self) -> reactivex.Observable[RandomPixelState]:
        return self._state

    def set_color(self, color: Color | None) -> None:
        current_state = self._state.value
        self._state.on_next(replace(current_state, color=color))

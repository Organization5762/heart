from __future__ import annotations

import random
from dataclasses import replace

import reactivex
from reactivex import operators as ops
from reactivex.subject import BehaviorSubject

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.random_pixel.state import RandomPixelState
from heart.renderers.state_provider import RngStateProvider
from heart.utilities.reactivex_threads import pipe_in_background


class RandomPixelStateProvider(RngStateProvider[RandomPixelState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        num_pixels: int,
        peripheral_manager: PeripheralManager,
        initial_color: Color | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(rng=rng)
        self._width = width
        self._height = height
        self._num_pixels = num_pixels
        self._peripheral_manager = peripheral_manager
        self._color = BehaviorSubject(initial_color)

    def observable(self) -> reactivex.Observable[RandomPixelState]:
        initial_color = self._color.value or Color.random()
        initial_state = RandomPixelState(
            color=initial_color, pixels=self._random_pixels()
        )

        color_updates = pipe_in_background(
            self._color,
            ops.map(lambda color: ("color", color)),
        )
        tick_updates = pipe_in_background(
            self._peripheral_manager.game_tick,
            ops.map(lambda _: ("tick", None)),
        )

        return pipe_in_background(
            reactivex.merge(color_updates, tick_updates),
            ops.scan(self._advance_state, seed=initial_state),
            ops.share(),
        )

    def set_color(self, color: Color | None) -> None:
        self._color.on_next(color)

    def _advance_state(
        self, state: RandomPixelState, event: tuple[str, Color | None]
    ) -> RandomPixelState:
        kind, value = event
        if kind == "color":
            next_color = value or Color.random()
            return replace(state, color=next_color)

        next_color = self._color.value or Color.random()
        return RandomPixelState(color=next_color, pixels=self._random_pixels())

    def _random_pixels(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (self.rng.randrange(self._width), self.rng.randrange(self._height))
            for _ in range(self._num_pixels)
        )

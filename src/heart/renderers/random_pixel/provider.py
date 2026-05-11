from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

import numpy as np
from manyfold import BehaviorSubject, MergeNode, StreamNode

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.random_pixel.state import RandomPixelState


class RandomPixelStateProvider(ObservableProvider[RandomPixelState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        num_pixels: int,
        peripheral_manager: PeripheralManager,
        initial_color: Color | None = None,
        randomness: RandomnessProvider,
        rng: random.Random | None = None,
        update_interval_ms: float = 100.0,
    ) -> None:
        self._width = width
        self._height = height
        self._num_pixels = num_pixels
        self._peripheral_manager = peripheral_manager
        self._color = BehaviorSubject(initial_color)
        self._rng = rng
        self._numpy_rng = randomness.numpy_rng()
        self._update_interval_ms = update_interval_ms
        self._elapsed_ms = 0.0

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[RandomPixelState]:
        initial_color = self._color.value or Color.random()
        initial_state = RandomPixelState(
            color=initial_color, pixels=self._random_pixels()
        )
        color_updates = self._color.map(lambda color: ("color", color))
        tick_updates = (
            self._peripheral_manager.frame_tick_controller.observable()
            .map(lambda frame_tick: ("tick", frame_tick))

        )
        return (
            MergeNode.merge(color_updates, tick_updates)
            .scan(self._advance_state, seed=initial_state)


        )

    def set_color(self, color: Color | None) -> None:
        self._color.on_next(color)

    def _advance_state(
        self, state: RandomPixelState, event: tuple[str, Color | Any]
    ) -> RandomPixelState:
        kind, value = event
        if kind == "color":
            next_color = value or Color.random()
            self._elapsed_ms = 0.0
            return replace(state, color=next_color)
        self._elapsed_ms += max(float(getattr(value, "delta_ms", 0.0)), 0.0)
        if self._elapsed_ms < self._update_interval_ms:
            return state
        self._elapsed_ms %= self._update_interval_ms
        next_color = self._color.value or Color.random()
        return RandomPixelState(color=next_color, pixels=self._random_pixels())

    def _random_pixels(self) -> tuple[tuple[int, int], ...]:
        if self._rng is None:
            pixels = self._numpy_rng.integers(
                low=(0, 0),
                high=(self._width, self._height),
                size=(self._num_pixels, 2),
                dtype=np.int16,
            )
            return tuple(map(tuple, pixels.tolist()))
        return tuple(
            (
                (self._rng.randrange(self._width), self._rng.randrange(self._height))
                for _ in range(self._num_pixels)
            )
        )

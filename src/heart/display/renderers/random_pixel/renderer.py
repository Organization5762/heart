from __future__ import annotations

import random
from typing import Callable

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import StatefulBaseRenderer
from heart.display.renderers.random_pixel.provider import \
    RandomPixelStateProvider
from heart.display.renderers.random_pixel.state import RandomPixelState


class RandomPixel(StatefulBaseRenderer[RandomPixelState]):
    def __init__(
        self,
        num_pixels: int = 1,
        color: Color | None = None,
        brightness: float = 1.0,
        provider_factory: Callable[[Color | None], RandomPixelStateProvider] | None = None,
    ) -> None:
        self.num_pixels = num_pixels
        self.brightness = brightness
        self._provider = (
            provider_factory(color)
            if provider_factory is not None
            else RandomPixelStateProvider(initial_color=color)
        )

        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        state = self.state

        pixels = [
            (random.randint(0, width - 1), random.randint(0, height - 1))
            for _ in range(self.num_pixels)
        ]

        base_color = state.color or Color.random()
        color_value = [int(x * self.brightness) for x in base_color._as_tuple()]

        for x, y in pixels:
            window.set_at((x, y), color_value)

    def set_color(self, color: Color | None) -> None:
        self._provider.set_color(color)

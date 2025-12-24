from __future__ import annotations

from typing import Callable

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.random_pixel.provider import RandomPixelStateProvider
from heart.renderers.random_pixel.state import RandomPixelState


class RandomPixel(StatefulBaseRenderer[RandomPixelState]):
    def __init__(
        self,
        num_pixels: int = 1,
        color: Color | None = None,
        brightness: float = 1.0,
        provider: RandomPixelStateProvider | None = None,
        provider_factory: Callable[..., RandomPixelStateProvider] | None = None,
    ) -> None:
        self.num_pixels = num_pixels
        self.brightness = brightness
        self._initial_color = color
        self._provider_factory = provider_factory or RandomPixelStateProvider
        self._provider: RandomPixelStateProvider | None = provider

        super().__init__(builder=provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is None:
            width, height = window.get_size()
            self._provider = self._provider_factory(
                width=width,
                height=height,
                num_pixels=self.num_pixels,
                peripheral_manager=peripheral_manager,
                initial_color=self._initial_color,
            )
            self.builder = self._provider
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state

        color_value = [int(x * self.brightness) for x in state.color._as_tuple()]

        for x, y in state.pixels:
            window.set_at((x, y), color_value)

    def set_color(self, color: Color | None) -> None:
        self._initial_color = color
        if self._provider is not None:
            self._provider.set_color(color)

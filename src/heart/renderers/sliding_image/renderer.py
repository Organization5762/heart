from __future__ import annotations

from typing import Callable

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.sliding_image.provider import (
    SlidingImageStateProvider, SlidingRendererStateProvider)
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)


class SlidingImage(StatefulBaseRenderer[SlidingImageState]):
    """Render a 256×64 image that continuously slides horizontally."""

    def __init__(
        self,
        image_file: str,
        *,
        speed: int = 1,
        provider_factory: Callable[[], SlidingImageStateProvider]
        | None = None,
    ) -> None:
        self._configured_speed = max(1, speed)
        self._image_file = image_file
        self._provider = (provider_factory or self._default_provider)()
        self._image: pygame.Surface | None = None

        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _default_provider(self) -> SlidingImageStateProvider:
        return SlidingImageStateProvider(speed=self._configured_speed)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlidingImageState]:
        return self._provider.observable(peripheral_manager=peripheral_manager)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._image is None or self._image.get_size() != window.get_size():
            image = Loader.load(self._image_file)
            self._image = pygame.transform.scale(image, window.get_size())
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        if self._image is None or self.state.width <= 0:
            return

        offset = self.state.offset
        width = self.state.width

        window.blit(self._image, (-offset, 0))
        if offset:
            window.blit(self._image, (width - offset, 0))


class SlidingRenderer(StatefulBaseRenderer[SlidingRendererState]):
    """Wrap another renderer and slide its output horizontally."""

    def __init__(
        self,
        renderer: StatefulBaseRenderer,
        *,
        speed: int = 1,
        provider_factory: Callable[[], SlidingRendererStateProvider]
        | None = None,
    ) -> None:
        self._configured_speed = max(1, speed)
        self.composed = renderer
        self._provider = (provider_factory or self._default_provider)()
        self._peripheral_manager: PeripheralManager | None = None

        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _default_provider(self) -> SlidingRendererStateProvider:
        return SlidingRendererStateProvider(speed=self._configured_speed)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlidingRendererState]:
        return self._provider.observable(peripheral_manager=peripheral_manager)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self.composed.initialize(window, clock, peripheral_manager, orientation)
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        if self._peripheral_manager is None:
            return

        self.composed._internal_process(
            window, clock, self._peripheral_manager, orientation
        )

        if self.state.width <= 0:
            return

        offset = self.state.offset
        width = self.state.width
        surface = window.copy()

        window.fill((0, 0, 0, 0))
        window.blit(surface, (-offset, 0))
        if offset:
            window.blit(surface, (width - offset, 0))

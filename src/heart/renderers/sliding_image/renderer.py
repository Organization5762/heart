from __future__ import annotations

from dataclasses import replace
from typing import Callable

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.sliding_image.provider import (
    SlidingImageStateProvider,
    SlidingRendererStateProvider,
)
from heart.renderers.sliding_image.state import (
    SlidingImageState,
    SlidingRendererState,
)
from heart.runtime.display_context import DisplayContext


class SlidingImage(StatefulBaseRenderer[SlidingImageState]):
    """Render a 256×64 image that continuously slides horizontally."""

    def __init__(
        self,
        image_file: str,
        *,
        speed: int = 1,
        provider_factory: Callable[[SlidingImageState], SlidingImageStateProvider]
        | None = None,
    ) -> None:
        self._image_file = image_file
        initial_state = SlidingImageState(speed=max(1, speed))
        self._provider = (provider_factory or self._default_provider)(initial_state)
        self._image: pygame.Surface | None = None

        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _default_provider(
        self, initial_state: SlidingImageState
    ) -> SlidingImageStateProvider:
        return SlidingImageStateProvider(initial_state=initial_state)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlidingImageState]:
        return self._provider.observable(peripheral_manager=peripheral_manager)

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._image is None or self._image.get_size() != window.get_size():
            image = Loader.load(self._image_file)
            self._image = pygame.transform.scale(image, window.get_size())
        if self._provider is not None and self._provider._initial_state is not None:
            self._provider._initial_state = replace(
                self._provider._initial_state,
                width=window.get_width(),
            )
        super().initialize(window, peripheral_manager, orientation)
        if self._state is not None:
            self.update_state(
                offset=self._provider.advance_state(
                    self._state, window.get_width()
                ).offset,
                width=window.get_width(),
            )

    def real_process(
        self,
        window: DisplayContext,
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
        provider_factory: Callable[[SlidingRendererState], SlidingRendererStateProvider]
        | None = None,
    ) -> None:
        self.composed = renderer
        initial_state = SlidingRendererState(speed=max(1, speed))
        self._provider = (provider_factory or self._default_provider)(initial_state)
        self._peripheral_manager: PeripheralManager | None = None

        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _default_provider(
        self, initial_state: SlidingRendererState
    ) -> SlidingRendererStateProvider:
        return SlidingRendererStateProvider(initial_state=initial_state)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlidingRendererState]:
        return self._provider.observable(peripheral_manager=peripheral_manager)

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self.composed.initialize(window, peripheral_manager, orientation)
        super().initialize(window, peripheral_manager, orientation)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if self._peripheral_manager is None:
            return

        self.composed._internal_process(
            window, self._peripheral_manager, orientation
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

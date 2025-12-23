from __future__ import annotations

from typing import Callable

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import BaseRenderer, StatefulBaseRenderer
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
        provider_factory: Callable[[PeripheralManager], SlidingImageStateProvider]
        | None = None,
    ) -> None:
        self._configured_speed = max(1, speed)
        self._image_file = image_file
        self._provider_factory = provider_factory
        self._provider: SlidingImageStateProvider | None = None

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def _ensure_provider(self, peripheral_manager: PeripheralManager) -> None:
        if self._provider is None:
            factory = self._provider_factory or (
                lambda manager: SlidingImageStateProvider(
                    manager, speed=self._configured_speed
                )
            )
            self._provider = factory(peripheral_manager)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._ensure_provider(peripheral_manager)
        assert self._provider is not None

        image = Loader.load(self._image_file)
        image = pygame.transform.scale(image, window.get_size())
        width, _ = image.get_size()

        self._provider.set_image(image)
        self._provider.set_width(width)
        if self.builder is None:
            self.builder = self._provider
        super().initialize(window, clock, peripheral_manager, orientation)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        image = self.state.image
        if image is None or self.state.width <= 0:
            return

        offset = self.state.offset
        width = self.state.width

        window.blit(image, (-offset, 0))
        if offset:
            window.blit(image, (width - offset, 0))

    def reset(self) -> None:
        if self._provider is not None:
            self._provider.request_reset()


class SlidingRenderer(StatefulBaseRenderer[SlidingRendererState]):
    """Wrap another renderer and slide its output horizontally."""

    def __init__(
        self,
        renderer: BaseRenderer,
        *,
        speed: int = 1,
        provider_factory: Callable[[PeripheralManager], SlidingRendererStateProvider]
        | None = None,
    ) -> None:
        self._configured_speed = max(1, speed)
        self.composed = renderer
        self._provider_factory = provider_factory
        self._provider: SlidingRendererStateProvider | None = None
        self._peripheral_manager: PeripheralManager | None = None

        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def _ensure_provider(self, peripheral_manager: PeripheralManager) -> None:
        if self._provider is None:
            factory = self._provider_factory or (
                lambda manager: SlidingRendererStateProvider(
                    manager, speed=self._configured_speed
                )
            )
            self._provider = factory(peripheral_manager)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._ensure_provider(peripheral_manager)
        assert self._provider is not None

        self.composed.initialize(window, clock, peripheral_manager, orientation)

        width, _ = window.get_size()
        self._provider.set_width(width)
        if self.builder is None:
            self.builder = self._provider
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

    def reset(self) -> None:
        if self._provider is not None:
            self._provider.request_reset()

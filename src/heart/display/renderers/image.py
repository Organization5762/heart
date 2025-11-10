from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.internal.event_stream import \
    RendererEventSubscriber
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class RenderImageState:
    image: pygame.Surface | None = None


class RenderImage(AtomicBaseRenderer[RenderImageState]):
    """Render an image sourced from an asset file or a renderer event stream."""

    def __init__(
        self,
        image_file: str | None = None,
        *,
        subscribe_channel: str | None = None,
        producer_id: int | None = None,
        subscriber_priority: int = 0,
    ) -> None:
        if image_file is None and subscribe_channel is None:
            raise ValueError(
                "RenderImage requires an image_file or subscribe_channel",
            )

        self._image_file = image_file
        self._subscribe_channel = subscribe_channel
        self._producer_id = producer_id
        self._subscriber_priority = subscriber_priority
        self._subscriber: RendererEventSubscriber | None = None
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(self) -> RenderImageState:
        return RenderImageState()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._subscribe_channel is not None:
            if self._subscriber is None:
                self._subscriber = RendererEventSubscriber(
                    channel=self._subscribe_channel,
                    producer_id=self._producer_id,
                    priority=self._subscriber_priority,
                )
            self._subscriber.initialize(window, clock, peripheral_manager, orientation)

        if self._image_file is not None:
            image = Loader.load(self._image_file).convert_alpha()
            image = pygame.transform.scale(image, window.get_size())
            self.update_state(image=image)

        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        rendered = False
        if self._subscriber is not None:
            has_frame = self._subscriber.has_frame()
            self._subscriber.process(window, clock, peripheral_manager, orientation)
            if has_frame:
                self.update_state(image=window.copy())
                rendered = True

        if not rendered and self.state.image is not None:
            window.blit(self.state.image, (0, 0))

    def reset(self) -> None:
        if self._subscriber is not None:
            self._subscriber.reset()
        super().reset()

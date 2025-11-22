from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class RenderImageState:
    image: pygame.Surface | None = None


class RenderImage(AtomicBaseRenderer[RenderImageState]):
    """Render an image sourced from an asset file or a renderer event stream."""

    def __init__(
        self,
        image_file: str,
        *,
        producer_id: int | None = None,
    ) -> None:
        self._image_file = image_file
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> RenderImageState:
        image = pygame.transform.scale(Loader.load(self._image_file).convert_alpha(), window.get_size())
        return RenderImageState(image=image)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        window.blit(self.state.image, (0, 0))

    def reset(self) -> None:
        if self._subscriber is not None:
            self._subscriber.reset()
        super().reset()

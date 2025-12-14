from typing import cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.image.state import RenderImageState


class RenderImageStateProvider(ObservableProvider[RenderImageState]):
    def __init__(self, image_file: str):
        self._image_file = image_file
        self._base_image: pygame.Surface | None = None

    def _load_base_image(self) -> pygame.Surface:
        if self._base_image is None:
            self._base_image = Loader.load(self._image_file).convert_alpha()
        return self._base_image

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[RenderImageState]:
        if peripheral_manager is None:
            raise ValueError("RenderImageStateProvider requires a PeripheralManager")

        window_stream = peripheral_manager.window.pipe(
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
        )

        base_image = self._load_base_image()

        def scale_to_window(size: tuple[int, int]) -> RenderImageState:
            scaled = pygame.transform.scale(base_image, size)
            return RenderImageState(image=scaled)

        return window_stream.pipe(ops.map(scale_to_window), ops.share())

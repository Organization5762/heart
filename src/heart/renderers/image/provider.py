from typing import cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.image.state import RenderImageState
from heart.utilities.reactivex_threads import pipe_in_background


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

        window_stream = pipe_in_background(
            peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
        )

        base_image = self._load_base_image()

        def build_state(size: tuple[int, int]) -> RenderImageState:
            return RenderImageState(base_image=base_image, window_size=size)

        return pipe_in_background(
            window_stream,
            ops.map(build_state),
            ops.share(),
        )

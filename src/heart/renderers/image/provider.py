from typing import cast

import pygame
from manyfold import StreamNode

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
    ) -> StreamNode[RenderImageState]:
        if peripheral_manager is None:
            raise ValueError("RenderImageStateProvider requires a PeripheralManager")
        window_stream = (
            peripheral_manager.window.filter(lambda window: window is not None)
            .map(lambda window: cast(pygame.Surface, window))
            .map(lambda window: window.get_size())
            .distinct_until_changed()

        )
        base_image = self._load_base_image()

        def build_state(size: tuple[int, int]) -> RenderImageState:
            return RenderImageState(base_image=base_image, window_size=size)

        return window_stream.map(build_state)


class SurfaceRenderImageStateProvider(ObservableProvider[RenderImageState]):
    def __init__(self, base_image: pygame.Surface):
        self._base_image = (
            base_image.convert_alpha()
            if pygame.display.get_surface() is not None
            else base_image.copy()
        )

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> StreamNode[RenderImageState]:
        if peripheral_manager is None:
            raise ValueError("SurfaceRenderImageStateProvider requires a PeripheralManager")
        window_stream = (
            peripheral_manager.window.filter(lambda window: window is not None)
            .map(lambda window: cast(pygame.Surface, window))
            .map(lambda window: window.get_size())
            .distinct_until_changed()
        )

        def build_state(size: tuple[int, int]) -> RenderImageState:
            return RenderImageState(base_image=self._base_image, window_size=size)

        return window_stream.map(build_state)

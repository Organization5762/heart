import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.surface_cache import RendererSurfaceCache
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseRenderer:
    @property
    def name(self):
        return self.__class__.__name__

    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.warmup = True
        self._surface_cache = RendererSurfaceCache()

    def is_initialized(self) -> bool:
        return self.initialized

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # We call process once incase there is any implicit cachable work to do
        # e.g. for numba jitted functions we'll cache their compiled code
        if self.warmup:
            screen = self._get_input_screen(window, orientation)
            self.process(screen, clock, peripheral_manager, orientation)
        self.initialized = True

    def reset(self):
        pass

    def get_renderers(self) -> list["BaseRenderer"]:
        return [self]

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        return self._surface_cache.get_input_screen(
            window=window,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

    def _postprocess_input_screen(
        self, screen: pygame.Surface, orientation: Orientation
    ):
        return self._surface_cache.postprocess_input_screen(
            screen=screen,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

    def _internal_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.is_initialized():
            self.initialize(window, clock, peripheral_manager, orientation)

        screen = self._get_input_screen(window, orientation)
        start_ns = time.perf_counter_ns()
        self.process(screen, clock, peripheral_manager, orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))
        logger.debug(
            "renderer.frame",  # structured logging friendly key
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
            },
        )

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        pass

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        return self._surface_cache.tile_surface(screen=screen, rows=rows, cols=cols)

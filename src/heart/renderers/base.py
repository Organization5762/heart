import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
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
            self.process(window, clock, peripheral_manager, orientation)
        self.initialized = True

    def reset(self):
        pass

    def get_renderers(self) -> list["BaseRenderer"]:
        return [self]

    def _internal_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.is_initialized():
            self.initialize(window, clock, peripheral_manager, orientation)

        start_ns = time.perf_counter_ns()
        self.process(window, clock, peripheral_manager, orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000

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
import time
from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Layout, Orientation
from heart.display.renderers.internal import FrameAccumulator
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseRenderer:
    supports_frame_accumulator: bool = False

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
        try:
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
        except Exception as e:
            logger.warning(f"Error initializing renderer ({type(self)}): {e}")
        self.initialized = True

    def reset(self):
        pass

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list["BaseRenderer"]:
        return [self]

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        window_x, window_y = window.get_size()

        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)
            case DeviceDisplayMode.OPENGL:
                # todo: this is actually completely unused for this dispaly mode
                #  so there's some smell here but providing this dummy val for now
                screen_size = (window_x, window_y)
        screen = pygame.Surface(screen_size, pygame.SRCALPHA)
        return screen

    def _postprocess_input_screen(
        self, screen: pygame.Surface, orientation: Orientation
    ):
        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen = self._tile_surface(
                    screen=screen, rows=layout.rows, cols=layout.columns
                )
            case DeviceDisplayMode.FULL:
                pass
        return screen

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
        if self.supports_frame_accumulator:
            accumulator = FrameAccumulator.from_surface(screen)
            self.process_with_accumulator(
                accumulator, clock, peripheral_manager, orientation
            )
            screen = accumulator.flush(screen)
        else:
            self.process(screen, clock, peripheral_manager, orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))
        logger.debug(
            "renderer.frame",  # structured logging friendly key
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
                "uses_accumulator": self.supports_frame_accumulator,
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

    def process_with_accumulator(
        self,
        accumulator: FrameAccumulator,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Render into a :class:`FrameAccumulator` (optional override)."""

        self.process(accumulator.surface, clock, peripheral_manager, orientation)

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        tiled_surface = pygame.Surface(
            (tile_width * cols, tile_height * rows), pygame.SRCALPHA
        )

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

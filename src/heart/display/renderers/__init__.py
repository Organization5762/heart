from dataclasses import dataclass

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager


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
        try:
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
        except Exception as e:
            print(f"Error initializing renderer: {e}")
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
        self.process(screen, clock, peripheral_manager, orientation)
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))

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

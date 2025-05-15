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
        self.x_offset = 0
        self.target_x_offset = 0
        self.slide_speed = 10  # pixels per frame
        self.sliding = False
        self.slide_enabled = False
        self.initialized = False

    def is_initialized(self) -> bool:
        return self.initialized

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.initialized = True

    def reset(self):
        pass

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list["BaseRenderer"]:
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

        self.process(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        pass

    def process_with_slide(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Process with sliding effect applied."""
        # Update sliding animation
        self._update_slide()

        # Create a temporary surface to draw content
        temp_surface = pygame.Surface(window.get_size(), pygame.SRCALPHA)

        self._internal_process(temp_surface, clock, peripheral_manager, orientation)

        # Draw the temp surface to the window with the offset
        window.blit(temp_surface, (self.x_offset, 0))

    def set_slide(self, from_x_offset: int, to_x_offset: int):
        self.target_x_offset = to_x_offset
        self.sliding = True
        self.slide_enabled = True
        self.x_offset = from_x_offset

    def _update_slide(self):
        if not self.sliding:
            return

        # Calculate distance to target
        distance = self.target_x_offset - self.x_offset

        # If we're very close to target, snap to it and stop sliding
        if abs(distance) < self.slide_speed:
            self.x_offset = self.target_x_offset
            self.sliding = False
            return

        # Otherwise move toward target
        self.x_offset += (distance / abs(distance)) * self.slide_speed


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

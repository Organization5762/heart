from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.device import Device
from heart.utilities.env import Configuration


@dataclass
class DisplayContext:
    """Track and initialize pygame display resources."""

    device: Device
    screen: pygame.Surface | None = None
    clock: pygame.time.Clock | None = None

    def configure_window(self, mode: int) -> None:
        self.scaled_screen = pygame.display.set_mode(
            (
                self.device.full_display_size()[0] * self.device.scale_factor,
                self.device.full_display_size()[1] * self.device.scale_factor,
            ),
            mode
        )
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            pygame.event.set_grab(True)

    def initialize(self, mode) -> None:
        pygame.init()
        self.screen = pygame.Surface(self.device.full_display_size(), mode)
        self.clock = pygame.time.Clock()

    def ensure_initialized(self) -> None:
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.device.set_screen(screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock

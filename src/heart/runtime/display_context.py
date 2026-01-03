from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.runtime.rendering.display import DisplayModeManager
from heart.utilities.env import Configuration


@dataclass
class DisplayContext:
    """Track and initialize pygame display resources."""

    device: Device
    screen: pygame.Surface | None = None
    clock: pygame.time.Clock | None = None
    _display_mode_manager: DisplayModeManager = field(init=False)

    def __post_init__(self) -> None:
        self._display_mode_manager = DisplayModeManager(self.device)

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

    def ensure_display_mode(self, display_mode: DeviceDisplayMode) -> None:
        self._display_mode_manager.ensure_mode(display_mode)

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.device.set_screen(screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock

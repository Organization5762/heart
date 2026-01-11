from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from heart import DeviceDisplayMode
from heart.device import Device, Layout, Orientation
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

@dataclass
class DisplayContext:
    """Track and initialize pygame display resources."""

    device: Device
    screen: pygame.Surface | None = None
    clock: pygame.time.Clock | None = None
    last_render_mode: DeviceDisplayMode | None = None

    def configure_window(self, device_display_mode: DeviceDisplayMode) -> None:
        self._ensure_mode(device_display_mode)

    def initialize(self) -> None:
        pygame.init()
        self._ensure_mode(DeviceDisplayMode.FULL)
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            pygame.event.set_grab(True)
        self.clock = pygame.time.Clock()

    def ensure_initialized(self) -> None:
        if self.clock is None or self.screen is None:
            raise RuntimeError("GameLoop failed to initialize display surfaces")

    def set_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.device.set_screen(screen)

    def set_clock(self, clock: pygame.time.Clock) -> None:
        self.clock = clock

    def _ensure_mode(self, display_mode: DeviceDisplayMode) -> None:
        target_mode = display_mode.to_pygame_mode()
        if self.last_render_mode == target_mode:
            return

        logger.info("Switching to %s mode", display_mode.name)

        pygame.display.init()
        self.screen = pygame.display.set_mode(self._display_size(), target_mode)
        self.last_render_mode = target_mode


    def _display_size(self) -> tuple[int, int]:
        return self.device.scaled_display_size()

    # Emulate screen
    def get_size(self) -> tuple[int, int]:
        return self.screen.get_size()

    def get_height(self) -> int:
        return self.screen.get_height()

    def get_width(self) -> int:
        return self.screen.get_width()

    def blit(self, *args, **kwargs) -> None:
        if self.screen is None:
            raise RuntimeError("Screen is not initialized")
        self.screen.blit(*args, **kwargs)

    def fill(self, *args, **kwargs) -> None:
        if self.screen is None:
            raise RuntimeError("Screen is not initialized")
        self.screen.fill(*args, **kwargs)

    def get_scratch_screen(self, orientation: Orientation, display_mode: DeviceDisplayMode) -> DisplayContext:
        window_x, window_y = self.get_size()
        match display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL | DeviceDisplayMode.OPENGL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)

        scratch_screen = pygame.Surface(screen_size, pygame.SRCALPHA)

        return DisplayContext(
            device=self.device,
            screen=scratch_screen,
            clock=self.clock,
            last_render_mode=self.last_render_mode,
        )

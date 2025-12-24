from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class DisplayModeManager:
    def __init__(self, device: Device) -> None:
        self._device = device
        self._last_render_mode = pygame.SHOWN

    def ensure_mode(self, display_mode: DeviceDisplayMode) -> None:
        target_mode = self._to_pygame_mode(display_mode)
        if self._last_render_mode == target_mode:
            return
        logger.info("Switching to %s mode", display_mode.name)
        pygame.display.set_mode(self._display_size(), target_mode)
        self._last_render_mode = target_mode

    def _display_size(self) -> tuple[int, int]:
        width, height = self._device.full_display_size()
        return (width * self._device.scale_factor, height * self._device.scale_factor)

    @staticmethod
    def _to_pygame_mode(display_mode: DeviceDisplayMode) -> int:
        if display_mode == DeviceDisplayMode.OPENGL:
            return pygame.OPENGL | pygame.DOUBLEBUF
        return pygame.SHOWN

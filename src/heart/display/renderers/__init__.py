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

    def get_renderers(self, peripheral_manager: PeripheralManager) -> list['BaseRenderer']:
        return [self]

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        None


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

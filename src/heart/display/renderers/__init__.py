import pygame

from heart.device import Orientation
from heart import DeviceDisplayMode
from heart.peripheral.manager import PeripheralManager


class BaseRenderer:
    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> None:
        None

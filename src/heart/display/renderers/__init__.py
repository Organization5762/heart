import pygame

from heart.environment import DeviceDisplayMode
from heart.peripherial.manager import PeripherialManager


class BaseRenderer:
    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def process(self, window: pygame.Surface, clock: pygame.time.Clock, peripherial_manager: PeripherialManager) -> None:
        None

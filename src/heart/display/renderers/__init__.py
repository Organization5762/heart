from heart.environment import DeviceDisplayMode

import pygame
class BaseRenderer:
    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED

    def process(self, window: pygame.Surface, clock: pygame.time.Clock) -> None:
        None

import math
import time

import pygame

from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager
import numpy as np

class Tixyland(BaseRenderer):
    def __init__(self, fn: callable) -> None:
        super().__init__()
        self.time_since_last_update = 0
        self.fn = fn

    def process(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> None:
        self.time_since_last_update += clock.get_time()
        # Convert from ms to seconds
        time_value = self.time_since_last_update / 1000

        arr = pygame.surfarray.pixels3d(window)
        h, w = window.get_height(), window.get_width()
        X, Y = np.meshgrid(np.arange(w), np.arange(h))
        I = X + Y * w

        numpy_output = self.fn(time_value, I, Y, X)
        numpy_output = np.clip(numpy_output, -1, 1)
        numpy_output = numpy_output * 255
        numpy_output = numpy_output.astype(np.float16)
        mag = np.abs(numpy_output)

        red   = mag[..., None] * np.array([1, 0, 0])
        white = mag[..., None] * np.array([1, 1, 1])

        rgb = np.where(numpy_output[..., None] < 0, red, white)
        
        pygame.surfarray.blit_array(window, rgb)
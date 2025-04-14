from collections import deque
import math
import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.environment import DeviceDisplayMode
from heart.peripheral.manager import PeripheralManager


class PythagoreanTiling(BaseRenderer):
    def __init__(self) -> None:
        self.device_display_mode = DeviceDisplayMode.FULL
        self.time_since_last_update = 0

        self.large_tile_color = Color.random()
        self.small_tile_color = Color.random()

    def pythagorean_tiling(self, window: Surface):
        # create an empty grid (2D array)
        
        # define square sizes
        square_a = 2
        square_b = 1
        
        x_size = window.get_size()[0]
        y_size = window.get_size()[1]

        # helper function to place a square on the grid
        def place_square(top_left_x, top_left_y, size, color):
            if top_left_x + size > x_size or top_left_y + size > y_size:
                return False  # can't place the square
            for i in range(top_left_x, top_left_x + x_size):
                for j in range(top_left_y, top_left_y + y_size):
                    window.set_at((i, j), color)
            return True
        
        # start placing squares on the grid
        x, y = 0, 0
        while x + square_a <= x_size and y + square_b <= y_size:
            place_square(x, y, square_a, (255, 0, 0))
            x += square_a  # move to next position
            place_square(x, y, square_b, (0, 255, 0))
            y += square_b  # move to next position
        
    def process(self, window: Surface, clock: Clock, peripheral_manager: PeripheralManager) -> None:
        self.time_since_last_update += clock.get_time()
        if self.time_since_last_update > 1000:
            self.pythagorean_tiling(window)
            self.time_since_last_update = 0
        
import math
from collections import deque

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class LSystem(BaseRenderer):
    def __init__(self) -> None:
        self.device_display_mode = DeviceDisplayMode.FULL
        self.grammar = "X"
        self.time_since_last_update = 0

    def _update_grammar(self):
        new_grammar = ""
        for char in self.grammar:
            if char == "X":
                new_grammar += "F+[[X]-X]-F[-FX]+X"
            elif char == "F":
                new_grammar += "FF"
            # if char == "F":
            #     new_grammar += "F+G"
            # elif char == "G":
            #     new_grammar += "F-G"
            # else:
            #     new_grammar += char
        self.grammar = new_grammar

    def _draw_grammar(self, window: Surface):
        # variables : F G
        # constants : + −
        # start  : F
        # rules  : (F → F+G), (G → F-G)
        # angle  : 90°
        # Here, F and G both mean "draw forward", + means "turn left by angle", and − means "turn right by angle". --> F+G−F−G+F

        # variables : X F
        # constants : + − [ ]
        # start  : X
        # rules  : (X → F+[[X]-X]-F[-FX]+X), (F → FF)
        # angle  : 25°

        angle = 25

        def calc_movement(L, angle):
            # Normalize angle between 0 and 360
            angle = angle % 360
            theta = math.radians(angle)
            x_movement = L * math.cos(theta)
            y_movement = L * math.sin(theta)
            return x_movement, y_movement

        min_length = 0
        for L in range(1, 100):
            x_move, y_move = calc_movement(L, angle)
            if x_move >= 1 and y_move >= 1:
                min_length = L
                break

        current_angle = 0
        position = np.array(window.get_size()) // 2
        stack = deque()
        for char in self.grammar:
            if char == "F" or char == "G":
                direction = calc_movement(min_length, current_angle)
                new_position = position + direction
                pygame.draw.line(window, (255, 255, 255), position, new_position)
                position = new_position
            elif char == "X":
                pass
            elif char == "+":
                current_angle += angle
            elif char == "-":
                current_angle -= angle
            elif char == "[":
                stack.append((position, current_angle))
            elif char == "]":
                position, current_angle = stack.pop()

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.time_since_last_update += clock.get_time()
        if self.time_since_last_update > 1000:
            self._update_grammar()
            self.time_since_last_update = 0
        self._draw_grammar(window)

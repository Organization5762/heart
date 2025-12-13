from __future__ import annotations

import math
from collections import deque

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import StatefulBaseRenderer
from heart.display.renderers.l_system.provider import LSystemStateProvider
from heart.display.renderers.l_system.state import LSystemState


class LSystem(StatefulBaseRenderer[LSystemState]):
    def __init__(self, builder: LSystemStateProvider) -> None:
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _draw_grammar(self, window: Surface, grammar: str) -> None:
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
        for char in grammar:
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

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        self._draw_grammar(window, self.state.grammar)

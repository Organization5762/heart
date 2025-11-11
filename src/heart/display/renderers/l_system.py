import math
from collections import deque
from dataclasses import dataclass

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class LSystemState:
    grammar: str = "X"
    time_since_last_update_ms: float = 0.0


class LSystem(AtomicBaseRenderer[LSystemState]):
    def __init__(self) -> None:
        AtomicBaseRenderer.__init__(self)
        self.device_display_mode = DeviceDisplayMode.FULL

    def _update_grammar(self, grammar: str) -> str:
        new_grammar = ""
        for char in grammar:
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
        return new_grammar

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

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        elapsed_ms = float(clock.get_time())
        state = self.state

        accumulated = state.time_since_last_update_ms + elapsed_ms
        grammar = state.grammar
        if accumulated > 1000:
            grammar = self._update_grammar(grammar)
            accumulated = 0.0

        self.update_state(
            grammar=grammar,
            time_since_last_update_ms=accumulated,
        )
        self._draw_grammar(window, grammar)

    def _create_initial_state(self) -> LSystemState:
        return LSystemState()

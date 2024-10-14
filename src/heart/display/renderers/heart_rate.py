import math
import random
from ast import Load
from dataclasses import dataclass
from shutil import move

import pygame

from heart.assets.loader import Loader
from heart.display import movement
from heart.display.movement import ChaoticOrbit, Orbit, UpAndDown
from heart.display.renderers import BaseRenderer, heart


@dataclass
class HeartRateState:
    bpm: int
    color: tuple[int, int, int]
    moving_direction: int = 1


class HeartRateUnit(BaseRenderer):
    def __init__(self, state: HeartRateState, movement) -> None:
        super().__init__()
        self.state = state

        self.animation = Loader.load_animation("web_heart_animation.png")
        self.movement = movement

    def process(self, window, clock, reference_objects) -> None:
        image = self.animation.step(window, clock)
        image.fill(self.state.color, special_flags=pygame.BLEND_MULT)
        self.movement.process(image, window, clock, reference_objects)
        return image


class HeartRate(BaseRenderer):
    def __init__(self) -> None:
        super().__init__()
        self.initialized = False
        self.heart_rate = None

    def _initialize(self, window) -> None:
        heart_rates = [
            HeartRateState(
                bpm=100,
                color=(219, 242, 39),
            ),
            HeartRateState(
                bpm=200,
                color=(255, 113, 206),
            ),
            HeartRateState(
                bpm=200,
                color=(185, 103, 255),
            ),
            HeartRateState(
                bpm=50,
                color=(1, 205, 254),
            ),
        ]

        self.heart_rates = [
            HeartRateUnit(state, ChaoticOrbit()) for state in heart_rates
        ]

        self.initialized = True

    def process(self, window, clock) -> None:
        if not self.initialized:
            self._initialize(window)

        locations = [x.movement.location for x in self.heart_rates]
        for _, heart_rate in enumerate(self.heart_rates):
            # Exclude self from locations
            l = locations.copy()
            l.remove(heart_rate.movement.location)
            heart_rate.process(window, clock, l)

from ast import Load
from dataclasses import dataclass
import math
import random
from heart.assets.loader import Loader
from heart.display.renderers import BaseRenderer, heart
import pygame

@dataclass
class HeartRateState:
    bpm: int
    color: tuple[int, int, int]
    location: tuple[int, int]
    moving_direction: int = 1

class HeartRateUnit():
    def __init__(self, state: HeartRateState) -> None:
        self.state = state

        self.animation = Loader.load_animation("web_heart_animation.png")

    def render(self, window, clock) -> None:
        image = self.animation.step(window, clock)
        image.fill(self.state.color, special_flags=pygame.BLEND_MULT)
        return image

    def move(self, delta: tuple[int, int]) -> None:
        self.state.location = (
            self.state.location[0] + delta[0],
            self.state.location[1] + delta[1] * self.state.moving_direction
        )

class HeartRate(BaseRenderer):
    def __init__(self) -> None:
        self.initialized = False

    def _initialize(self, window) -> None:
        heart_rates = [
            HeartRateState(
                bpm=100,
                color=(219, 242, 39),
                location=(
                    random.randint(0, window.get_width() - 50 - 1),
                    random.randint(0, window.get_height() - 100 - 1)
                )
            ),
            HeartRateState(
                bpm=200,
                color=(255, 113, 206),
                location=(
                    random.randint(0, window.get_width() - 50 - 1),
                    random.randint(0, window.get_height() - 100 - 1)
                )
            ),
            HeartRateState(
                bpm=200,
                color=(185, 103, 255),
                location=(
                    random.randint(0, window.get_width() - 50 - 1),
                    random.randint(0, window.get_height() - 100 - 1)
                )
            ),
            HeartRateState(
                bpm=50,
                color=(1, 205, 254),
                location=(
                    random.randint(0, window.get_width() - 50 - 1),
                    random.randint(0, window.get_height() - 100 - 1)
                )
            ),
        ]

        # Equally spaced X locations
        for i, state in enumerate(heart_rates):
            state.location = (
                ((window.get_width() / len(heart_rates)) * i) + 25,
                state.location[1]
            )

        self.heart_rates = [
            HeartRateUnit(state) for state in heart_rates
        ]

        self.initialized = True

    def process(self, window, clock) -> None:
        if not self.initialized:
            self._initialize(window)

        for _, heart_rate in enumerate(self.heart_rates):
            # TODO: Could also do waterfall?
            image = heart_rate.render(window, clock)
            if heart_rate.state.location[1] >= (window.get_height() - 100):
                heart_rate.state.moving_direction = -1
            elif heart_rate.state.location[1] <= 0:
                heart_rate.state.moving_direction = 1



            heart_rate.move((0, random.choices([1, 2], [200 - heart_rate.state.bpm, heart_rate.state.bpm], k=1)[0]))

            window.blit(image, heart_rate.state.location)
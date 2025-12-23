from __future__ import annotations

import pygame
from pygame.time import Clock

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.three_fractal.renderer import FractalRuntime
from heart.renderers.three_fractal.state import FractalSceneState


class FractalSceneProvider:
    def __init__(self, device=None) -> None:
        self.device = device

    def initial_state(
        self,
        window: pygame.Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FractalSceneState:
        runtime = FractalRuntime(device=self.device)
        runtime.initialize(window, clock, peripheral_manager, orientation)
        return FractalSceneState(runtime=runtime)

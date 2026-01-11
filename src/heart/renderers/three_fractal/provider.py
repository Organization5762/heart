from __future__ import annotations

import pygame
import reactivex
from pygame.time import Clock

from heart.device import Device, Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.three_fractal.state import FractalSceneState
from heart.runtime.display_context import DisplayContext


class FractalSceneProvider(ObservableProvider[FractalSceneState]):
    def __init__(self, device: Device) -> None:
        self.device = device

    def initial_state(
        self,
        window: DisplayContext,

        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> FractalSceneState:
        from heart.renderers.three_fractal.renderer import FractalRuntime

        runtime = FractalRuntime(device=self.device)
        runtime.initialize(window, peripheral_manager, orientation)
        return FractalSceneState(runtime=runtime)

    def observable(
        self, *, initial_state: FractalSceneState
    ) -> reactivex.Observable[FractalSceneState]:
        return reactivex.just(initial_state)

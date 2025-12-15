from __future__ import annotations

import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.hilbert_curve.provider import HilbertCurveProvider
from heart.renderers.hilbert_curve.state import HilbertCurveState


class HilbertScene(StatefulBaseRenderer[HilbertCurveState]):
    def __init__(self, provider: HilbertCurveProvider | None = None) -> None:
        self.provider = provider or HilbertCurveProvider()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.line_color = (215, 72, 148)
        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> HilbertCurveState:
        width, height = window.get_size()
        return self.provider.initial_state(width=width, height=height)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.provider.advance(self.state, now=time.time())
        self.set_state(state)

        window.fill((0, 0, 0))
        if len(state.frame_curve) > 1:
            pygame.draw.lines(window, self.line_color, False, state.frame_curve, 1)


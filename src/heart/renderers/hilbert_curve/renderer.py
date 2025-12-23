from __future__ import annotations

import pygame
import reactivex

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
        super().__init__(builder=self.provider)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[HilbertCurveState]:
        return self.provider.observable(peripheral_manager)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        window.fill((0, 0, 0))
        if len(state.frame_curve) > 1:
            pygame.draw.lines(window, self.line_color, False, state.frame_curve, 1)

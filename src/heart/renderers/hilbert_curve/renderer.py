from __future__ import annotations

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.hilbert_curve.provider import HilbertCurveProvider
from heart.renderers.hilbert_curve.state import HilbertCurveState
from heart.runtime.display_context import DisplayContext


class HilbertScene(StatefulBaseRenderer[HilbertCurveState]):
    def __init__(self, provider: HilbertCurveProvider | None = None) -> None:
        self.provider = provider or HilbertCurveProvider()
        self._initial_state: HilbertCurveState | None = None
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.line_color = (215, 72, 148)
        super().__init__(builder=self.provider)

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        self._initial_state = self.provider.initial_state(width=width, height=height)
        super().initialize(window, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[HilbertCurveState]:
        if self._initial_state is None:
            raise ValueError("HilbertScene requires an initial state")
        return self.provider.observable(
            peripheral_manager,
            initial_state=self._initial_state,
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        window.screen.fill((0, 0, 0))
        if len(state.frame_curve) > 1:
            pygame.draw.lines(window.screen, self.line_color, False, state.frame_curve, 1)

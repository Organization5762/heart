from __future__ import annotations

import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.channel_diffusion.provider import \
    ChannelDiffusionStateProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState
from heart.runtime.display_context import DisplayContext


class ChannelDiffusionRenderer(StatefulBaseRenderer[ChannelDiffusionState]):
    def __init__(self, provider: ChannelDiffusionStateProvider) -> None:
        self._provider = provider
        self._initial_state: ChannelDiffusionState | None = None
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.FULL
        self.warmup = False

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        self._initial_state = self._provider.initial_state(width=width, height=height)
        super().initialize(window, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[ChannelDiffusionState]:
        if self._initial_state is None:
            raise ValueError("ChannelDiffusionRenderer requires an initial state")
        return self._provider.observable(
            peripheral_manager,
            initial_state=self._initial_state,
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        pygame.surfarray.blit_array(window, self.state.grid)

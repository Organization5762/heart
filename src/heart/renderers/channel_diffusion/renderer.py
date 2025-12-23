from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.channel_diffusion.provider import \
    ChannelDiffusionStateProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionRenderer(StatefulBaseRenderer[ChannelDiffusionState]):
    def __init__(self, provider: ChannelDiffusionStateProvider | None = None) -> None:
        self._provider = provider or ChannelDiffusionStateProvider()
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.warmup = False

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ChannelDiffusionState:
        width, height = window.get_size()
        initial_state = self._provider.initial_state(width=width, height=height)
        self.set_state(initial_state)
        self._subscription = self._provider.observable(
            peripheral_manager,
            initial_state=initial_state,
        ).subscribe(on_next=self.set_state)
        return initial_state

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        pygame.surfarray.blit_array(window, self.state.grid)

from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import AtomicBaseRenderer
from heart.renderers.channel_diffusion.provider import \
    ChannelDiffusionStateProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionRenderer(AtomicBaseRenderer[ChannelDiffusionState]):
    def __init__(self, provider: ChannelDiffusionStateProvider | None = None) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.warmup = False
        self._provider = provider or ChannelDiffusionStateProvider()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ChannelDiffusionState:
        width, height = window.get_size()
        return self._provider.initial_state(width=width, height=height)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        next_state = self._provider.next_state(self.state)
        self.set_state(next_state)

        pygame.surfarray.blit_array(window, next_state.grid)

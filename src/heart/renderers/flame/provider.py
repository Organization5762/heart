from __future__ import annotations

import pygame
from manyfold import StreamNode
from manyfold.architecture import Value

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.flame.state import FlameState


class FlameStateProvider(ObservableProvider[FlameState]):
    def __init__(self) -> None:
        self._initial_time = pygame.time.get_ticks() * 2 / 1000.0
        self._initial_state = FlameState(
            time_seconds=self._initial_time, dt_seconds=0.0
        )
        self._latest_state = Value.initialized(self._initial_state)

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> StreamNode[FlameState]:
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()

        def to_state(frame_tick: object) -> FlameState:
            return FlameState(
                time_seconds=pygame.time.get_ticks() * 2 / 1000.0,
                dt_seconds=max(frame_tick.delta_s, 1.0 / 120.0),
            )

        return (
            frame_ticks.map(to_state)
            .do_action(self._latest_state.set)
            .start_with(self._initial_state)
        )

    @property
    def latest_state(self) -> FlameState:
        latest = self._latest_state.latest
        if latest is None:
            return self._initial_state
        return latest

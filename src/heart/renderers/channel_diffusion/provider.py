from __future__ import annotations

import numpy as np
from manyfold import StreamNode

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionStateProvider(ObservableProvider[ChannelDiffusionState]):
    def initial_state(self, *, width: int, height: int) -> ChannelDiffusionState:
        grid = np.zeros((height, width, 3), dtype=np.uint8)
        grid[height // 2, width // 2] = np.array([255, 255, 255], dtype=np.uint8)
        return ChannelDiffusionState(grid=grid)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: ChannelDiffusionState,
    ) -> StreamNode[ChannelDiffusionState]:
        initial_size = (initial_state.grid.shape[1], initial_state.grid.shape[0])
        window_sizes = (
            peripheral_manager.window.filter(lambda window: window is not None)
            .map(lambda window: window.get_size())
            .distinct_until_changed()
            .start_with(initial_size)

        )
        ticks = peripheral_manager.input_io.frame_tick_stream()

        def build_stream(
            size: tuple[int, int],
        ) -> StreamNode[ChannelDiffusionState]:
            seeded_state = self.initial_state(width=size[0], height=size[1])
            return (
                ticks.scan(lambda state, _: self.next_state(state), seed=seeded_state)
                .start_with(seeded_state)

            )

        return window_sizes.map(build_stream).switch_latest()

    def next_state(self, state: ChannelDiffusionState) -> ChannelDiffusionState:
        grid = state.grid.astype(np.int32)
        red = grid[:, :, 0]
        green = grid[:, :, 1]
        blue = grid[:, :, 2]
        new_grid = np.zeros_like(grid)
        center = self._compute_center_after_fade(grid)
        new_grid += center
        new_grid[:, :-1, 1] += green[:, 1:]
        new_grid[:, 1:, 1] += green[:, :-1]
        new_grid[:-1, :, 2] += blue[1:, :]
        new_grid[1:, :, 2] += blue[:-1, :]
        new_grid[:-1, :-1, 0] += red[1:, 1:]
        new_grid[1:, :-1, 0] += red[:-1, 1:]
        new_grid[:-1, 1:, 0] += red[1:, :-1]
        new_grid[1:, 1:, 0] += red[:-1, :-1]
        clipped_grid = np.clip(new_grid, 0, 255).astype(np.uint8)
        return ChannelDiffusionState(grid=clipped_grid)

    def _compute_center_after_fade(self, grid: np.ndarray) -> np.ndarray:
        brightness = grid.max(axis=2)
        return grid - (brightness // 2)[:, :, None]

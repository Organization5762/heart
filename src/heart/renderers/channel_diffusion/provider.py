from __future__ import annotations

import numpy as np
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionStateProvider(ObservableProvider[ChannelDiffusionState]):
    def initial_state(self, *, width: int, height: int) -> ChannelDiffusionState:
        grid = np.zeros((width, height, 3), dtype=np.uint8)
        grid[width // 2, height // 2] = np.array([255, 255, 255], dtype=np.uint8)
        return ChannelDiffusionState(grid=grid)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: ChannelDiffusionState,
    ) -> reactivex.Observable[ChannelDiffusionState]:
        initial_size = (initial_state.grid.shape[0], initial_state.grid.shape[1])
        window_sizes = peripheral_manager.window.pipe(
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
            ops.start_with(initial_size),
        )

        ticks = peripheral_manager.game_tick.pipe(
            ops.filter(lambda tick: tick is not None),
        )

        def build_stream(
            size: tuple[int, int],
        ) -> reactivex.Observable[ChannelDiffusionState]:
            seeded_state = self.initial_state(width=size[0], height=size[1])
            return ticks.pipe(
                ops.scan(lambda state, _: self.next_state(state), seed=seeded_state),
                ops.start_with(seeded_state),
            )

        return window_sizes.pipe(
            ops.map(build_stream),
            ops.switch_latest(),
            ops.share(),
        )

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

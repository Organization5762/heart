from __future__ import annotations

import numpy as np
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.channel_diffusion.state import ChannelDiffusionState
from heart.utilities.reactivex_threads import pipe_in_background


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
    ) -> reactivex.Observable[ChannelDiffusionState]:
        initial_size = (initial_state.grid.shape[1], initial_state.grid.shape[0])
        window_sizes = pipe_in_background(
            peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
            ops.start_with(initial_size),
        )

        ticks = pipe_in_background(
            peripheral_manager.game_tick,
            ops.filter(lambda tick: tick is not None),
        )

        def build_stream(
            size: tuple[int, int],
        ) -> reactivex.Observable[ChannelDiffusionState]:
            seeded_state = self.initial_state(width=size[0], height=size[1])
            return pipe_in_background(
                ticks,
                ops.scan(lambda state, _: self.next_state(state), seed=seeded_state),
                ops.start_with(seeded_state),
            )

        return pipe_in_background(
            window_sizes,
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

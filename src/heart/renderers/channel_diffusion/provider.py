from __future__ import annotations

import numpy as np

from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionStateProvider:
    def initial_state(self, *, width: int, height: int) -> ChannelDiffusionState:
        grid = np.zeros((width, height, 3), dtype=np.uint8)
        grid[width // 2, height // 2] = np.array([255, 255, 255], dtype=np.uint8)
        return ChannelDiffusionState(grid=grid)

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

from __future__ import annotations

import numpy as np
import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import AtomicBaseRenderer
from heart.renderers.channel_diffusion.state import ChannelDiffusionState


class ChannelDiffusionRenderer(AtomicBaseRenderer[ChannelDiffusionState]):
    def __init__(self) -> None:
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
        grid = np.zeros((width, height, 3), dtype=np.uint8)
        grid[width // 2, height // 2] = np.array([255, 255, 255], dtype=np.uint8)
        return ChannelDiffusionState(grid=grid)

    def _compute_center_after_fade(self, grid: np.ndarray) -> np.ndarray:
        brightness = grid.max(axis=2)
        faded = grid - (brightness // 2)[:, :, None]
        return faded

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        grid = self.state.grid.astype(np.int32)

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
        self.set_state(ChannelDiffusionState(grid=clipped_grid))

        pygame.surfarray.blit_array(window, clipped_grid)

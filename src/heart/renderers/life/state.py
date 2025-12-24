import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.ndimage import convolve

from heart.utilities.env import Configuration, LifeUpdateStrategy

DEFAULT_LIFE_KERNEL = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=int)


@dataclass
class LifeState:
    grid: np.ndarray
    cache_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kernel: np.ndarray | None = field(default=None)

    def _update_grid(self) -> Any:
        kernel = self.kernel
        strategy = Configuration.life_update_strategy()

        if kernel is None and strategy in {
            LifeUpdateStrategy.AUTO,
            LifeUpdateStrategy.PAD,
        }:
            neighbors = _count_neighbors_with_padding(self.grid)
        else:
            if kernel is None:
                kernel = DEFAULT_LIFE_KERNEL
            if kernel is not None and strategy == LifeUpdateStrategy.PAD:
                raise ValueError(
                    "HEART_LIFE_UPDATE_STRATEGY='pad' only supports the default kernel."
                )
            neighbors = convolve(self.grid, kernel, mode="constant", cval=0)

        new_grid = (neighbors == 3) | (self.grid & (neighbors == 2))

        assert new_grid.shape == self.grid.shape, "Grid size must match"

        new_grid = new_grid.astype(int)
        return LifeState(grid=new_grid, cache_id=self.cache_id, kernel=self.kernel)


def _count_neighbors_with_padding(grid: np.ndarray) -> np.ndarray:
    padded = np.pad(grid, 1, mode="constant")
    return (
        padded[:-2, :-2]
        + padded[:-2, 1:-1]
        + padded[:-2, 2:]
        + padded[1:-1, :-2]
        + padded[1:-1, 2:]
        + padded[2:, :-2]
        + padded[2:, 1:-1]
        + padded[2:, 2:]
    )

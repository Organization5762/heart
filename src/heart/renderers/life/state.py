import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.ndimage import convolve

from heart.utilities.env import (Configuration, LifeRuleStrategy,
                                 LifeUpdateStrategy)

DEFAULT_LIFE_KERNEL = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]], dtype=int)
LIFE_RULE_TABLE = np.array(
    [
        [0, 0, 0, 1, 0, 0, 0, 0, 0],
        [0, 0, 1, 1, 0, 0, 0, 0, 0],
    ],
    dtype=int,
)


@dataclass
class LifeState:
    grid: np.ndarray
    cache_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kernel: np.ndarray | None = field(default=None)
    neighbor_buffer: np.ndarray | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @staticmethod
    def resolve_rng(seed: int | None = None) -> np.random.Generator:
        return np.random.default_rng(seed)

    @classmethod
    def random_grid(
        cls, size: tuple[int, int], rng: np.random.Generator | None = None
    ) -> np.ndarray:
        if rng is None:
            rng = cls.resolve_rng()
        return rng.integers(0, 2, size=size, dtype=int)

    def _update_grid(self) -> Any:
        kernel = self.kernel
        strategy = Configuration.life_update_strategy()
        neighbors = self._resolve_neighbors(kernel, strategy)
        new_grid = self._apply_rules(neighbors)

        assert new_grid.shape == self.grid.shape, "Grid size must match"

        new_grid = new_grid.astype(int)
        return LifeState(
            grid=new_grid,
            cache_id=self.cache_id,
            kernel=self.kernel,
            neighbor_buffer=self.neighbor_buffer,
        )

    def _resolve_neighbors(
        self, kernel: np.ndarray | None, strategy: LifeUpdateStrategy
    ) -> np.ndarray:
        if strategy == LifeUpdateStrategy.AUTO:
            return self._auto_neighbors(kernel)
        if strategy == LifeUpdateStrategy.PAD:
            if kernel is not None:
                raise ValueError(
                    "HEART_LIFE_UPDATE_STRATEGY='pad' only supports the default kernel."
                )
            return _count_neighbors_with_padding(self.grid)
        if strategy == LifeUpdateStrategy.SHIFTED:
            if kernel is not None:
                raise ValueError(
                    "HEART_LIFE_UPDATE_STRATEGY='shifted' only supports the default kernel."
                )
            return _count_neighbors_shifted(self.grid, self._ensure_neighbor_buffer())

        if kernel is None:
            kernel = DEFAULT_LIFE_KERNEL
        return self._convolve_neighbors(kernel)

    def _apply_rules(self, neighbors: np.ndarray) -> np.ndarray:
        rule_strategy = Configuration.life_rule_strategy()
        if rule_strategy == LifeRuleStrategy.DIRECT:
            return self._apply_direct_rules(neighbors)
        if rule_strategy == LifeRuleStrategy.TABLE:
            return self._apply_table_rules(neighbors)
        if self._can_use_rule_table(neighbors):
            return self._apply_table_rules(neighbors)
        return self._apply_direct_rules(neighbors)

    def _apply_direct_rules(self, neighbors: np.ndarray) -> np.ndarray:
        return (neighbors == 3) | (self.grid & (neighbors == 2))

    def _apply_table_rules(self, neighbors: np.ndarray) -> np.ndarray:
        if not self._can_use_rule_table(neighbors):
            return self._apply_direct_rules(neighbors)
        return LIFE_RULE_TABLE[self.grid, neighbors]

    def _can_use_rule_table(self, neighbors: np.ndarray) -> bool:
        if self.kernel is not None and not np.array_equal(
            self.kernel, DEFAULT_LIFE_KERNEL
        ):
            return False
        if not np.issubdtype(neighbors.dtype, np.integer):
            return False
        min_value = int(neighbors.min())
        max_value = int(neighbors.max())
        return min_value >= 0 and max_value <= 8

    def _auto_neighbors(self, kernel: np.ndarray | None) -> np.ndarray:
        if kernel is not None:
            return self._convolve_neighbors(kernel)

        threshold = Configuration.life_convolve_threshold()
        if threshold > 0 and self.grid.size >= threshold:
            return self._convolve_neighbors(DEFAULT_LIFE_KERNEL)
        return _count_neighbors_shifted(self.grid, self._ensure_neighbor_buffer())

    def _convolve_neighbors(self, kernel: np.ndarray) -> np.ndarray:
        neighbors = self._ensure_neighbor_buffer(
            dtype=np.result_type(self.grid, kernel)
        )
        convolve(self.grid, kernel, mode="constant", cval=0, output=neighbors)
        return neighbors

    def _ensure_neighbor_buffer(self, dtype: np.dtype | None = None) -> np.ndarray:
        if dtype is None:
            dtype = np.result_type(self.grid, np.int16)
        dtype = np.dtype(dtype)
        if (
            self.neighbor_buffer is None
            or self.neighbor_buffer.shape != self.grid.shape
            or self.neighbor_buffer.dtype != dtype
        ):
            self.neighbor_buffer = np.zeros(self.grid.shape, dtype=dtype)
        else:
            self.neighbor_buffer.fill(0)
        return self.neighbor_buffer


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


def _count_neighbors_shifted(
    grid: np.ndarray, neighbors: np.ndarray
) -> np.ndarray:
    neighbors.fill(0)
    neighbors[1:, 1:] += grid[:-1, :-1]
    neighbors[1:, :] += grid[:-1, :]
    neighbors[1:, :-1] += grid[:-1, 1:]
    neighbors[:, 1:] += grid[:, :-1]
    neighbors[:, :-1] += grid[:, 1:]
    neighbors[:-1, 1:] += grid[1:, :-1]
    neighbors[:-1, :] += grid[1:, :]
    neighbors[:-1, :-1] += grid[1:, 1:]
    return neighbors

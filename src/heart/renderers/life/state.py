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
    def resolve_rng(
        seed: int | None, rng: np.random.Generator | None = None
    ) -> np.random.Generator:
        if rng is not None:
            return rng
        return np.random.default_rng(seed)

    @staticmethod
    def random_grid(
        size: tuple[int, int], rng: np.random.Generator
    ) -> np.ndarray:
        return rng.integers(0, 2, size=size, dtype=int)

    def _update_grid(self) -> Any:
        kernel = self.kernel
        strategy = Configuration.life_update_strategy()
        rule_strategy = Configuration.life_rule_strategy()
        neighbors = self._resolve_neighbors(kernel, strategy)
        new_grid = self._apply_rules(neighbors, kernel, rule_strategy)

        assert new_grid.shape == self.grid.shape, "Grid size must match"

        new_grid = new_grid.astype(int)
        return LifeState(
            grid=new_grid,
            cache_id=self.cache_id,
            kernel=self.kernel,
            neighbor_buffer=self.neighbor_buffer,
        )

    def _apply_rules(
        self,
        neighbors: np.ndarray,
        kernel: np.ndarray | None,
        strategy: LifeRuleStrategy,
    ) -> np.ndarray:
        if strategy == LifeRuleStrategy.DIRECT:
            return self._apply_direct_rules(neighbors)
        if strategy == LifeRuleStrategy.TABLE:
            return self._apply_table_rules(neighbors, kernel)
        if kernel is not None:
            return self._apply_direct_rules(neighbors)
        return self._apply_table_rules(neighbors, kernel)

    def _apply_direct_rules(self, neighbors: np.ndarray) -> np.ndarray:
        return (neighbors == 3) | (self.grid & (neighbors == 2))

    def _apply_table_rules(
        self, neighbors: np.ndarray, kernel: np.ndarray | None
    ) -> np.ndarray:
        if kernel is not None:
            return self._apply_direct_rules(neighbors)
        if neighbors.size == 0:
            return neighbors.astype(int)
        if np.max(neighbors) > 8 or np.min(neighbors) < 0:
            return self._apply_direct_rules(neighbors)
        state_index = self.grid.astype(np.int8, copy=False)
        neighbor_index = neighbors.astype(np.int8, copy=False)
        return LIFE_RULE_TABLE[state_index, neighbor_index]

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

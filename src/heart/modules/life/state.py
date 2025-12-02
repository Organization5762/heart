import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.ndimage import convolve


@dataclass
class LifeState:
    grid: np.ndarray
    cache_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kernel: np.ndarray | None = field(default=None)

    def _update_grid(self) -> Any:
        kernel = self.kernel
        if kernel is None:
            kernel = np.array([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
        
        # Count the number of neighbors
        neighbors = convolve(self.grid, kernel, mode="constant", cval=0)
        new_grid = (neighbors == 3) | (self.grid & (neighbors == 2))

        assert new_grid.shape == self.grid.shape, "Grid size must match"

        new_grid =  new_grid.astype(int)
        return LifeState(grid=new_grid, cache_id=self.cache_id)
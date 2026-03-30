from __future__ import annotations

import hashlib
import random

import numpy as np

from heart.utilities.env import Configuration


class RandomnessProvider:
    """Build seeded RNGs for providers from a shared project seed."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = Configuration.random_seed() if seed is None else seed

    @property
    def seed(self) -> int | None:
        return self._seed

    def rng(self, namespace: str | None = None) -> random.Random:
        return random.Random(self.seed_for(namespace))

    def numpy_rng(self, namespace: str | None = None) -> np.random.Generator:
        return np.random.default_rng(self.seed_for(namespace))

    def seed_for(self, namespace: str | None = None) -> int | None:
        if self.seed is None or namespace is None:
            return self.seed
        seed_material = f"{self.seed}:{namespace}".encode("utf-8")
        digest = hashlib.sha256(seed_material).digest()
        return int.from_bytes(digest[:8], "big")

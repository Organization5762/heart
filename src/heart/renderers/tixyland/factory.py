from __future__ import annotations

from typing import Callable

import numpy as np

from heart.renderers.tixyland.provider import TixylandStateProvider
from heart.renderers.tixyland.renderer import Tixyland


class TixylandFactory:
    def __init__(self, provider_factory: Callable[[], TixylandStateProvider]) -> None:
        self._provider_factory = provider_factory

    def __call__(
        self,
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    ) -> Tixyland:
        return Tixyland(builder=self._provider_factory(), fn=fn)

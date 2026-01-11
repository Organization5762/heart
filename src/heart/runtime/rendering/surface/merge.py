from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import assert_never

import pygame

from heart.runtime.rendering.composition import SurfaceComposer
from heart.utilities.env import Configuration, RenderMergeStrategy


class SurfaceCompositionManager:
    def __init__(
        self,
        composer: SurfaceComposer | None = None,
        strategy_provider: RenderMergeStrategy | None = None,
    ) -> None:
        self._composer = composer or SurfaceComposer()
        self._strategy_provider = strategy_provider or Configuration.render_merge_strategy()

    def _merge_in_place(
        self, surface1: pygame.Surface, surface2: pygame.Surface
    ) -> pygame.Surface:
        assert surface1.get_size() == surface2.get_size(), (
            "Surfaces must be the same size to merge."
        )
        surface1.blit(surface2, (0, 0))
        return surface1

    def compose_serial(
        self,
        surfaces: list[pygame.Surface],
    ) -> pygame.Surface | None:
        if not surfaces:
            return None
        match self._strategy_provider:
            case RenderMergeStrategy.IN_PLACE:
                base = surfaces[0]
                for surface in surfaces[1:]:
                    base = self._merge_in_place(base, surface)
                return base
            case _:
                assert_never(self._strategy_provider)

from __future__ import annotations

import random
import time

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

from .renderer import (
    DEFAULT_PAPER_PATH,
    DEFAULT_ROCK_PATH,
    DEFAULT_SCISSORS_PATH,
    RNG_NAMESPACE,
    THROW_NAMES,
)
from .state import RockPaperScissorsPhase, RockPaperScissorsState

TITLE_BACKGROUND_COLOR = (0, 0, 0)
TITLE_IMAGE_HEIGHT_RATIO = 0.75
TITLE_IMAGE_WIDTH_RATIO = 0.85


class RockPaperScissorsTitle(StatefulBaseRenderer[RockPaperScissorsState]):
    """Title screen that shows a randomly chosen throw image."""

    def __init__(
        self,
        *,
        randomness: RandomnessProvider | None = None,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._rng = rng or (randomness or RandomnessProvider()).rng(RNG_NAMESPACE)
        self._throw_paths = {
            "paper": DEFAULT_PAPER_PATH,
            "rock": DEFAULT_ROCK_PATH,
            "scissors": DEFAULT_SCISSORS_PATH,
        }
        self._asset_mtimes_ns: dict[str, int] = {}
        self._images: dict[str, pygame.Surface] = {}
        self._scaled_cache: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        self._last_frame_time: float | None = None

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> RockPaperScissorsState:
        del peripheral_manager, orientation
        self._ensure_assets_loaded(window)
        return RockPaperScissorsState(
            phase=RockPaperScissorsPhase.REVEAL,
            phase_started_at=0.0,
            selected_throw=self._rng.choice(THROW_NAMES),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        self._ensure_assets_loaded(window)
        now = time.monotonic()
        if self._last_frame_time is None or (now - self._last_frame_time) > 0.5:
            self.set_state(
                RockPaperScissorsState(
                    phase=RockPaperScissorsPhase.REVEAL,
                    phase_started_at=0.0,
                    selected_throw=self._rng.choice(THROW_NAMES),
                )
            )
        self._last_frame_time = now
        window_width, window_height = window.get_size()

        max_w = int(window_width * TITLE_IMAGE_WIDTH_RATIO)
        max_h = int(window_height * TITLE_IMAGE_HEIGHT_RATIO)
        throw = self.state.selected_throw
        base = self._images[throw]
        scale = min(max_w / base.get_width(), max_h / base.get_height())
        target = (
            max(1, int(base.get_width() * scale)),
            max(1, int(base.get_height() * scale)),
        )

        cache_key = (throw, target)
        scaled = self._scaled_cache.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.scale(base, target)
            self._scaled_cache[cache_key] = scaled

        x = (window_width - scaled.get_width()) // 2
        y = (window_height - scaled.get_height()) // 2 - 4
        window.blit(scaled, (x, y))

    def reset(self) -> None:
        self.set_state(
            RockPaperScissorsState(
                phase=RockPaperScissorsPhase.REVEAL,
                phase_started_at=0.0,
                selected_throw=self._rng.choice(THROW_NAMES),
            )
        )

    def _ensure_assets_loaded(self, window: DisplayContext) -> None:
        if window.screen is None:
            raise RuntimeError(
                "RockPaperScissorsTitle requires an initialized display surface"
            )
        assets_changed = False
        for name, path in self._throw_paths.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing Rock Paper Scissors asset: {path}"
                )
            modified_at_ns = path.stat().st_mtime_ns
            if self._asset_mtimes_ns.get(name) == modified_at_ns:
                continue
            self._images[name] = pygame.image.load(path).convert_alpha()
            self._asset_mtimes_ns[name] = modified_at_ns
            assets_changed = True
        if assets_changed:
            self._scaled_cache.clear()

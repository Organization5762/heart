from __future__ import annotations

import random
import time
from pathlib import Path

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

from .state import RockPaperScissorsPhase, RockPaperScissorsState

DOCUMENTS_ASSET_DIR = Path.home() / "Documents"
DEFAULT_PAPER_PATH = DOCUMENTS_ASSET_DIR / "Paper.png"
DEFAULT_ROCK_PATH = DOCUMENTS_ASSET_DIR / "Rock.png"
DEFAULT_SCISSORS_PATH = DOCUMENTS_ASSET_DIR / "Scissors.png"
DEFAULT_MIDDLE_PATH = DOCUMENTS_ASSET_DIR / "Middle.png"
PIXEL_FONT_PATH = "Grand9K Pixel.ttf"
BACKGROUND_COLOR = (0, 0, 0)
COUNTDOWN_LABELS = ("", "Rock", "Paper", "Scissors")
COUNTDOWN_BOUNCE_CYCLES = len(COUNTDOWN_LABELS)
REVEAL_LABEL = "Go"
COUNTDOWN_BOTTOM_HOLD_PORTION = 0.12
COUNTDOWN_RISE_PORTION = 0.72
COUNTDOWN_IMAGE_HEIGHT_RATIO = 0.78
REVEAL_IMAGE_WIDTH_RATIO = 0.9
COUNTDOWN_FONT_SIZE = 12
COUNTDOWN_MIN_FONT_SIZE = 8
COUNTDOWN_TEXT_COLOR = (255, 255, 255)
RNG_NAMESPACE = "rock-paper-scissors"
THROW_NAMES = ("paper", "rock", "scissors")
MIDDLE_THROW_NAME = "middle"
MIDDLE_THROW_CHANCE_DENOMINATOR = 30


class RockPaperScissorsRenderer(StatefulBaseRenderer[RockPaperScissorsState]):
    def __init__(
        self,
        *,
        paper_path: Path = DEFAULT_PAPER_PATH,
        rock_path: Path = DEFAULT_ROCK_PATH,
        scissors_path: Path = DEFAULT_SCISSORS_PATH,
        middle_path: Path = DEFAULT_MIDDLE_PATH,
        randomness: RandomnessProvider | None = None,
        rng: random.Random | None = None,
        intro_duration_s: float = 2.4,
        countdown_duration_s: float = 4.0,
        reveal_duration_s: float = 1.8,
        bounce_offset_px: int = 14,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        del intro_duration_s
        self._countdown_duration_s = countdown_duration_s
        self._reveal_duration_s = reveal_duration_s
        self._bounce_offset_px = bounce_offset_px
        self._rng = rng or (randomness or RandomnessProvider()).rng(RNG_NAMESPACE)
        self._throw_paths = {
            "paper": paper_path,
            "rock": rock_path,
            "scissors": scissors_path,
            MIDDLE_THROW_NAME: middle_path,
        }
        self._asset_mtimes_ns: dict[str, int] = {}
        self._images: dict[str, pygame.Surface] = {}
        self._scaled_images: dict[tuple[str, tuple[int, int]], pygame.Surface] = {}
        self._fonts: dict[int, pygame.font.Font] = {}
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
            phase=RockPaperScissorsPhase.COUNTDOWN,
            phase_started_at=time.monotonic(),
            selected_throw=self._random_reveal_throw(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        if window.screen is None:
            raise RuntimeError(
                "RockPaperScissorsRenderer requires an initialized display surface"
            )

        self._ensure_assets_loaded(window)
        now = time.monotonic()
        if self._last_frame_time is None or (now - self._last_frame_time) > 0.5:
            self.set_state(
                RockPaperScissorsState(
                    phase=RockPaperScissorsPhase.COUNTDOWN,
                    phase_started_at=now,
                    selected_throw=self._random_reveal_throw(),
                )
            )
        self._last_frame_time = now
        self._advance_phase(now)
        window.fill(BACKGROUND_COLOR)

        match self.state.phase:
            case RockPaperScissorsPhase.INTRO | RockPaperScissorsPhase.COUNTDOWN:
                self._render_countdown(window, now)
            case RockPaperScissorsPhase.REVEAL:
                self._render_reveal(window)

    def reset(self) -> None:
        self._last_frame_time = None
        self.set_state(
            RockPaperScissorsState(
                phase=RockPaperScissorsPhase.COUNTDOWN,
                phase_started_at=time.monotonic(),
                selected_throw=self._random_reveal_throw(),
            )
        )

    def _ensure_assets_loaded(self, window: DisplayContext) -> None:
        if window.screen is None:
            raise RuntimeError(
                "RockPaperScissorsRenderer requires an initialized display surface"
            )
        assets_changed = False
        for throw_name, image_path in self._throw_paths.items():
            if not image_path.exists():
                raise FileNotFoundError(
                    f"Missing Rock Paper Scissors asset: {image_path}"
                )
            modified_at_ns = image_path.stat().st_mtime_ns
            if self._asset_mtimes_ns.get(throw_name) == modified_at_ns:
                continue
            self._images[throw_name] = pygame.image.load(image_path).convert_alpha()
            self._asset_mtimes_ns[throw_name] = modified_at_ns
            assets_changed = True
        if assets_changed:
            self._scaled_images.clear()

    def _advance_phase(self, now: float) -> None:
        while True:
            phase = self.state.phase
            elapsed = now - self.state.phase_started_at
            if phase is RockPaperScissorsPhase.INTRO:
                self.set_state(
                    RockPaperScissorsState(
                        phase=RockPaperScissorsPhase.COUNTDOWN,
                        phase_started_at=now,
                        selected_throw=self.state.selected_throw,
                    )
                )
                continue
            if phase is RockPaperScissorsPhase.COUNTDOWN:
                if elapsed < self._countdown_duration_s:
                    return
                self.set_state(
                    RockPaperScissorsState(
                        phase=RockPaperScissorsPhase.REVEAL,
                        phase_started_at=now,
                        selected_throw=self.state.selected_throw,
                    )
                )
                continue
            if elapsed < self._reveal_duration_s:
                return
            self.set_state(
                RockPaperScissorsState(
                    phase=RockPaperScissorsPhase.COUNTDOWN,
                    phase_started_at=now,
                    selected_throw=self._random_reveal_throw(),
                )
            )
            return

    def _render_countdown(self, window: DisplayContext, now: float) -> None:
        cycle_index = self._current_bounce_cycle(now)
        label = COUNTDOWN_LABELS[cycle_index]
        window_width, window_height = window.get_size()

        if label:
            label_surface = self._countdown_label_surface(
                label, max_width=max(1, window_width - 4)
            )
            label_x = (window_width - label_surface.get_width()) // 2
            label_y = 4
            window.blit(label_surface, (label_x, label_y))

        rock_surface = self._scaled_image(
            "rock",
            max_width=int(window_width * REVEAL_IMAGE_WIDTH_RATIO),
            max_height=int(window_height * COUNTDOWN_IMAGE_HEIGHT_RATIO),
        )
        anchor_y = (window_height // 2) + 12
        bounce_offset = self._countdown_bounce_offset(now, window_height=window_height)
        rock_x = (window_width - rock_surface.get_width()) // 2
        rock_y = anchor_y - (rock_surface.get_height() // 2) + bounce_offset
        window.blit(rock_surface, (rock_x, rock_y))

    def _render_reveal(self, window: DisplayContext) -> None:
        window_width, window_height = window.get_size()
        label_surface = self._countdown_label_surface(
            REVEAL_LABEL, max_width=max(1, window_width - 4)
        )
        label_x = (window_width - label_surface.get_width()) // 2
        label_y = 4
        window.blit(label_surface, (label_x, label_y))

        reveal_surface = self._scaled_image(
            self.state.selected_throw,
            max_width=int(window_width * REVEAL_IMAGE_WIDTH_RATIO),
            max_height=int(window_height * COUNTDOWN_IMAGE_HEIGHT_RATIO),
        )
        anchor_y = (window_height // 2) + 12
        x_offset = (window_width - reveal_surface.get_width()) // 2
        y_offset = anchor_y - (reveal_surface.get_height() // 2)
        window.blit(reveal_surface, (x_offset, y_offset))

    def _current_bounce_cycle(self, now: float) -> int:
        elapsed = max(0.0, now - self.state.phase_started_at)
        cycle_duration = self._countdown_duration_s / COUNTDOWN_BOUNCE_CYCLES
        return min(int(elapsed / cycle_duration), COUNTDOWN_BOUNCE_CYCLES - 1)

    def _countdown_bounce_offset(self, now: float, *, window_height: int) -> int:
        elapsed = max(0.0, now - self.state.phase_started_at)
        cycle_duration = self._countdown_duration_s / COUNTDOWN_BOUNCE_CYCLES
        cycle_progress = (elapsed % cycle_duration) / cycle_duration
        amplitude = max(self._bounce_offset_px, int(window_height * 0.18))

        if cycle_progress <= COUNTDOWN_BOTTOM_HOLD_PORTION:
            return 0

        if cycle_progress <= COUNTDOWN_RISE_PORTION:
            rise_progress = (cycle_progress - COUNTDOWN_BOTTOM_HOLD_PORTION) / (
                COUNTDOWN_RISE_PORTION - COUNTDOWN_BOTTOM_HOLD_PORTION
            )
            return int(round(-amplitude * rise_progress))

        drop_progress = (cycle_progress - COUNTDOWN_RISE_PORTION) / (
            1 - COUNTDOWN_RISE_PORTION
        )
        eased_drop = (1 - drop_progress) ** 2
        return int(round(-amplitude * eased_drop))

    def _countdown_label_surface(
        self,
        label: str,
        *,
        max_width: int,
    ) -> pygame.Surface:
        for font_size in range(COUNTDOWN_FONT_SIZE, COUNTDOWN_MIN_FONT_SIZE - 1, -1):
            font = self._font(font_size)
            surface = font.render(label, False, COUNTDOWN_TEXT_COLOR)
            if surface.get_width() <= max_width:
                return surface
        return self._font(COUNTDOWN_MIN_FONT_SIZE).render(
            label, False, COUNTDOWN_TEXT_COLOR
        )

    def _scaled_image(
        self,
        throw_name: str,
        *,
        max_width: int,
        max_height: int,
    ) -> pygame.Surface:
        base_image = self._images[throw_name]
        width = base_image.get_width()
        height = base_image.get_height()
        scale = min(max_width / width, max_height / height)
        target_size = (
            max(1, int(width * scale)),
            max(1, int(height * scale)),
        )
        cache_key = (throw_name, target_size)
        scaled = self._scaled_images.get(cache_key)
        if scaled is None:
            scaled = pygame.transform.scale(base_image, target_size)
            self._scaled_images[cache_key] = scaled
        return scaled

    def _font(self, size: int) -> pygame.font.Font:
        font = self._fonts.get(size)
        if font is None:
            font = Loader.load_font(PIXEL_FONT_PATH, font_size=size)
            self._fonts[size] = font
        return font

    def _random_throw(self) -> str:
        return self._rng.choice(THROW_NAMES)

    def _random_reveal_throw(self) -> str:
        if self._rng.randrange(MIDDLE_THROW_CHANCE_DENOMINATOR) == 0:
            return MIDDLE_THROW_NAME
        return self._random_throw()

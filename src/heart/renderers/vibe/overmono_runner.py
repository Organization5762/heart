from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.assets.spritesheet import Spritesheet
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

OVERMONO_SHEET_PATH = Path("vibe") / "overmono_64x64_spritesheet.png"
OVERMONO_FRAME_SIZE = 64
OVERMONO_FRAME_COUNT = 2
OVERMONO_FRAME_DURATION_MS = 375
OVERMONO_TRAVEL_DURATION_MS = 3000
OVERMONO_BACKGROUND = (255, 112, 32)


@dataclass(frozen=True)
class OvermonoRunnerState:
    spritesheet: Spritesheet
    start_ticks_ms: int


class OvermonoRunner(StatefulBaseRenderer[OvermonoRunnerState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._scaled_frame: pygame.Surface | None = None
        self._scaled_frame_key: tuple[int, int, int] | None = None

    def _create_initial_state(
        self,
        *,
        window: DisplayContext,
        peripheral_manager,
        orientation: Orientation,
    ) -> OvermonoRunnerState:
        del window, peripheral_manager, orientation
        return OvermonoRunnerState(
            spritesheet=Loader.load_spirtesheet(OVERMONO_SHEET_PATH),
            start_ticks_ms=pygame.time.get_ticks(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        state = self.state
        window_width, window_height = window.get_size()
        window.fill(OVERMONO_BACKGROUND)

        current_ticks = pygame.time.get_ticks()
        elapsed_ms = current_ticks - state.start_ticks_ms
        frame_index = (elapsed_ms // OVERMONO_FRAME_DURATION_MS) % OVERMONO_FRAME_COUNT

        sprite_height = window_height
        sprite_width = window_height
        frame_key = (frame_index, sprite_width, sprite_height)
        if self._scaled_frame is None or self._scaled_frame_key != frame_key:
            frame_rect = (
                frame_index * OVERMONO_FRAME_SIZE,
                0,
                OVERMONO_FRAME_SIZE,
                OVERMONO_FRAME_SIZE,
            )
            self._scaled_frame = state.spritesheet.image_at_scaled(
                frame_rect,
                (sprite_width, sprite_height),
            )
            self._scaled_frame_key = frame_key

        assert self._scaled_frame is not None
        cycle_progress = (elapsed_ms % OVERMONO_TRAVEL_DURATION_MS) / OVERMONO_TRAVEL_DURATION_MS
        start_x = window_width
        end_x = -sprite_width
        x = round(start_x + (end_x - start_x) * cycle_progress)
        window.blit(self._scaled_frame, (x, 0))

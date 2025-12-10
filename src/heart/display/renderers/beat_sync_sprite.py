"""Beat-synced spritesheet animation.

Advances animation frames on each beat detected by BeatFlashRenderer.
"""

import time
from dataclasses import dataclass
from typing import Any

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.beat_state import get_beat_state
from heart.display.renderers import AtomicBaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass
class BeatSyncSpriteState:
    """State for beat-synced sprite animation."""

    spritesheet: Any = None  # heart.assets.loader.spritesheet
    current_frame: int = 0
    last_beat_number: int = -1
    frame_count: int = 1
    frame_height: int = 32
    last_change_time: float = 0.0


class BeatSyncSprite(AtomicBaseRenderer[BeatSyncSpriteState]):
    """Spritesheet that advances one frame per beat.

    Uses the shared beat state from BeatFlashRenderer to sync animation
    to detected music beats.
    """

    def __init__(
        self,
        sheet_file_path: str,
        frame_width: int = 64,
        frame_height: int | None = None,
        scale: float = 1.0,
        frames_per_beat: int = 1,
    ) -> None:
        """Initialize beat-synced sprite.

        Args:
            sheet_file_path: Path to horizontal spritesheet
            frame_width: Width of each frame in pixels
            frame_height: Height of each frame (defaults to sheet height)
            scale: Scale factor for display
            frames_per_beat: How many frames to advance per beat
        """
        self.sheet_file_path = sheet_file_path
        self.frame_width = frame_width
        self._frame_height = frame_height
        self.scale = scale
        self.frames_per_beat = frames_per_beat
        super().__init__()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BeatSyncSpriteState:
        spritesheet = Loader.load_spirtesheet(self.sheet_file_path)
        sheet_width, sheet_height = spritesheet.get_size()

        frame_height = self._frame_height or sheet_height
        frame_count = sheet_width // self.frame_width

        return BeatSyncSpriteState(
            spritesheet=spritesheet,
            current_frame=0,
            last_beat_number=-1,
            frame_count=frame_count,
            frame_height=frame_height,
        )

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        """Render sprite, advancing frame on each beat."""
        state = self.state
        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        # Check beat state
        beat_state = get_beat_state()
        current_beat = beat_state.get_beat_number()

        print(
            f"current_beat: {current_beat}, state.last_beat_number: {state.last_beat_number}, beat_state.interval: {beat_state.interval}"
        )
        # Advance frame if beat changed
        if current_beat != state.last_beat_number and beat_state.interval is not None:
            now = time.monotonic()
            since_last = (
                now - state.last_change_time if state.last_change_time > 0 else 0.0
            )
            new_frame = (state.current_frame + self.frames_per_beat) % state.frame_count
            print(
                f"[SPRITE] beat {state.last_beat_number} -> {current_beat}, frame {state.current_frame} -> {new_frame} (+{since_last:.3f}s)"
            )
            self.update_state(
                current_frame=new_frame,
                last_beat_number=current_beat,
                last_change_time=now,
            )
            state = self.state

        # Extract current frame using spritesheet.image_at()
        frame_x = state.current_frame * self.frame_width
        frame_rect = (frame_x, 0, self.frame_width, state.frame_height)
        frame_surface = spritesheet.image_at(frame_rect)

        # Scale if needed
        if self.scale != 1.0:
            new_width = int(self.frame_width * self.scale)
            new_height = int(state.frame_height * self.scale)
            frame_surface = pygame.transform.scale(
                frame_surface, (new_width, new_height)
            )

        # Center on screen
        screen_width, screen_height = window.get_size()
        frame_width, frame_height = frame_surface.get_size()
        x = (screen_width - frame_width) // 2
        y = (screen_height - frame_height) // 2

        window.blit(frame_surface, (x, y))

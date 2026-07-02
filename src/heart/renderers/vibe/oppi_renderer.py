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

OPPI_GIF_SHEET_PATH = Path("vibe") / "oppi_gif_64x64_spritesheet.png"
OPPI_STATIC_IMAGE_PATH = Path("vibe") / "oppi_static_64x64.png"
OPPI_FRAME_SIZE = 64
OPPI_FRAME_COUNT = 116
OPPI_FRAME_DURATION_MS = 48


@dataclass(frozen=True)
class OppiState:
    gif_spritesheet: Spritesheet
    static_image: pygame.Surface
    start_ticks_ms: int


class OppiRenderer(StatefulBaseRenderer[OppiState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._scaled_static: pygame.Surface | None = None
        self._scaled_static_size: tuple[int, int] | None = None
        self._scaled_gif_frame: pygame.Surface | None = None
        self._scaled_gif_frame_key: tuple[int, int, int] | None = None

    def _create_initial_state(
        self,
        *,
        window: DisplayContext,
        peripheral_manager,
        orientation: Orientation,
    ) -> OppiState:
        del window, peripheral_manager, orientation
        return OppiState(
            gif_spritesheet=Loader.load_spirtesheet(OPPI_GIF_SHEET_PATH),
            static_image=Loader.load(OPPI_STATIC_IMAGE_PATH),
            start_ticks_ms=pygame.time.get_ticks(),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        window_width, window_height = window.get_size()
        columns = max(1, orientation.layout.columns)
        rows = max(1, orientation.layout.rows)
        panel_width = window_width // columns
        panel_height = window_height // rows
        panel_size = (panel_width, panel_height)

        current_ticks = pygame.time.get_ticks()
        elapsed_ms = current_ticks - state.start_ticks_ms
        frame_index = (elapsed_ms // OPPI_FRAME_DURATION_MS) % OPPI_FRAME_COUNT

        if self._scaled_static is None or self._scaled_static_size != panel_size:
            self._scaled_static = pygame.transform.scale(state.static_image, panel_size)
            self._scaled_static_size = panel_size

        gif_frame_key = (frame_index, panel_width, panel_height)
        if (
            self._scaled_gif_frame is None
            or self._scaled_gif_frame_key != gif_frame_key
        ):
            frame_rect = (
                frame_index * OPPI_FRAME_SIZE,
                0,
                OPPI_FRAME_SIZE,
                OPPI_FRAME_SIZE,
            )
            gif_frame = state.gif_spritesheet.image_at(frame_rect)
            self._scaled_gif_frame = pygame.transform.scale(gif_frame, panel_size)
            self._scaled_gif_frame_key = gif_frame_key

        for row in range(rows):
            for column in range(columns):
                destination = (column * panel_width, row * panel_height)
                use_gif = (row + column) % 2 == 0
                surface = self._scaled_gif_frame if use_gif else self._scaled_static
                assert surface is not None
                window.blit(surface, destination)

from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.renderers import StatefulBaseRenderer
from heart.peripheral.rubiks_connected_x import rubiks_connected_x_face_slice
from heart.renderers.rubiks_connected_x_visualizer.provider import (
    RubiksConnectedXVisualizerStateProvider,
)
from heart.renderers.rubiks_connected_x_visualizer.state import (
    RubiksConnectedXVisualizerState,
)
from heart.runtime.display_context import DisplayContext

FRAME_BACKGROUND = (4, 6, 10)
UNSYNCED_STICKER = (44, 48, 58)
GRID_LINE_COLOR = (8, 10, 14)
FACE_SEPARATOR_COLOR = (2, 3, 5)
FACE_SEPARATOR_WIDTH_PX = 4
STICKER_COLORS = {
    "U": (245, 245, 245),
    "R": (214, 45, 32),
    "F": (22, 163, 74),
    "D": (250, 204, 21),
    "L": (249, 115, 22),
    "B": (37, 99, 235),
}


class RubiksConnectedXVisualizerRenderer(
    StatefulBaseRenderer[RubiksConnectedXVisualizerState]
):
    """Render four cube faces across the 4-panel strip."""

    def __init__(
        self,
        provider: RubiksConnectedXVisualizerStateProvider | None = None,
    ) -> None:
        super().__init__(builder=provider or RubiksConnectedXVisualizerStateProvider())
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        width, height = window.get_size()
        facelets = self.state.facelets or ""
        face_count = len(self.state.visible_faces)
        face_size = min(height, width // face_count)
        strip_width = face_size * face_count
        strip_left = max(0, (width - strip_width) // 2)
        row_edges = _partition_span(0, face_size, 3)

        window.screen.fill(FRAME_BACKGROUND)
        for face_index, face_label in enumerate(self.state.visible_faces):
            face_left = strip_left + (face_index * face_size)
            face_rect = pygame.Rect(face_left, 0, face_size, face_size)
            self._draw_face(
                screen=window.screen,
                face_rect=face_rect,
                face_index=face_index,
                stickers=(
                    rubiks_connected_x_face_slice(facelets, face_label)
                    if facelets
                    else None
                ),
                row_edges=row_edges,
            )

        for edge in row_edges[1:-1]:
            pygame.draw.line(
                window.screen,
                GRID_LINE_COLOR,
                (strip_left, edge),
                (strip_left + strip_width - 1, edge),
                width=1,
            )
        for separator_index in range(1, face_count):
            edge = strip_left + (separator_index * face_size)
            pygame.draw.line(
                window.screen,
                FACE_SEPARATOR_COLOR,
                (edge, 0),
                (edge, face_size - 1),
                width=FACE_SEPARATOR_WIDTH_PX,
            )

    def _draw_face(
        self,
        *,
        screen: pygame.Surface,
        face_rect: pygame.Rect,
        face_index: int,
        stickers: str | None,
        row_edges: list[int],
    ) -> None:
        sticker_source = stickers or "?" * 9
        column_edges = _partition_span(face_rect.left, face_rect.width, 3)
        for row_index in range(3):
            for column_index in range(3):
                sticker_index = row_index * 3 + column_index
                color = STICKER_COLORS.get(
                    sticker_source[sticker_index],
                    UNSYNCED_STICKER,
                )
                sticker_rect = pygame.Rect(
                    column_edges[column_index],
                    row_edges[row_index],
                    column_edges[column_index + 1] - column_edges[column_index],
                    row_edges[row_index + 1] - row_edges[row_index],
                )
                pygame.draw.rect(screen, color, sticker_rect)
        for edge in column_edges[1:-1]:
            pygame.draw.line(
                screen,
                GRID_LINE_COLOR,
                (edge, face_rect.top),
                (edge, face_rect.bottom - 1),
                width=1,
            )


def _partition_span(start: int, size: int, cells: int) -> list[int]:
    """Return integer boundaries that exactly tile a span into `cells` slices."""

    return [start + ((size * index) // cells) for index in range(cells)] + [
        start + size
    ]

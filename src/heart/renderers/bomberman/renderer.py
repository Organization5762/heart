from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.bomberman.provider import BombermanStateProvider
from heart.renderers.bomberman.state import BombermanState, Coord
from heart.runtime.display_context import DisplayContext

BACKGROUND = (12, 15, 22)
FLOOR = (34, 42, 49)
FLOOR_ALT = (29, 36, 43)
HARD_WALL = (72, 82, 92)
HARD_WALL_HIGHLIGHT = (108, 120, 132)
SOFT_BLOCK = (154, 92, 42)
SOFT_BLOCK_HIGHLIGHT = (215, 145, 70)
BOMB = (9, 9, 13)
BOMB_FUSE = (255, 90, 54)
FLAME = (255, 191, 56)
FLAME_CORE = (255, 244, 180)
PLAYER = (47, 211, 231)
PLAYER_FACE = (8, 32, 44)
CLEARED_TINT = (30, 145, 88)
DEAD_TINT = (128, 24, 36)
GRID_SIZE = 16


class BombermanRenderer(StatefulBaseRenderer[BombermanState]):
    def __init__(
        self,
        builder: BombermanStateProvider | None = None,
    ) -> None:
        super().__init__(builder=builder)
        self.device_display_mode = DeviceDisplayMode.FULL

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is None:
            self.builder = BombermanStateProvider()
        super().initialize(window, peripheral_manager, orientation)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        if window.screen is None:
            raise RuntimeError("BombermanRenderer requires an initialized display surface")

        window.fill(BACKGROUND)
        cell_px, offset = self._board_geometry(window)
        self._draw_floor(window.screen, cell_px, offset)
        self._draw_cells(window.screen, self.state.soft_blocks, SOFT_BLOCK, cell_px, offset)
        self._draw_cells(window.screen, self.state.walls, HARD_WALL, cell_px, offset)
        self._draw_wall_highlights(window.screen, cell_px, offset)
        self._draw_flames(window.screen, cell_px, offset)
        self._draw_bombs(window.screen, cell_px, offset)
        self._draw_player(window.screen, cell_px, offset)
        self._draw_phase_tint(window.screen, cell_px, offset)

    def _board_geometry(self, window: DisplayContext) -> tuple[int, Coord]:
        width, height = window.get_size()
        cell_px = max(1, min(width, height) // GRID_SIZE)
        board_px = cell_px * GRID_SIZE
        return cell_px, ((width - board_px) // 2, (height - board_px) // 2)

    def _draw_floor(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                color = FLOOR if (x + y) % 2 == 0 else FLOOR_ALT
                pygame.draw.rect(surface, color, self._rect((x, y), cell_px, offset))

    def _draw_cells(
        self,
        surface: pygame.Surface,
        cells: frozenset[Coord],
        color: tuple[int, int, int],
        cell_px: int,
        offset: Coord,
    ) -> None:
        for cell in cells:
            pygame.draw.rect(surface, color, self._rect(cell, cell_px, offset))
            if color == SOFT_BLOCK and cell_px >= 3:
                rect = self._rect(cell, cell_px, offset)
                pygame.draw.line(
                    surface,
                    SOFT_BLOCK_HIGHLIGHT,
                    rect.topleft,
                    (rect.right - 1, rect.top),
                )

    def _draw_wall_highlights(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        if cell_px < 3:
            return
        for cell in self.state.walls:
            rect = self._rect(cell, cell_px, offset)
            pygame.draw.line(
                surface,
                HARD_WALL_HIGHLIGHT,
                (rect.left, rect.top),
                (rect.right - 1, rect.top),
            )

    def _draw_bombs(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        for bomb in self.state.bombs:
            rect = self._rect(bomb.position, cell_px, offset).inflate(
                -max(0, cell_px // 3),
                -max(0, cell_px // 3),
            )
            pygame.draw.ellipse(surface, BOMB, rect)
            if cell_px >= 4:
                fuse_x = rect.centerx
                pygame.draw.line(
                    surface,
                    BOMB_FUSE,
                    (fuse_x, rect.top),
                    (fuse_x, max(rect.top, rect.top - 1)),
                )

    def _draw_flames(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        for flame in self.state.flames:
            rect = self._rect(flame.position, cell_px, offset)
            pygame.draw.rect(surface, FLAME, rect)
            if cell_px >= 3:
                pygame.draw.rect(surface, FLAME_CORE, rect.inflate(-2, -2))

    def _draw_player(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        if self.state.phase == "dead":
            color = (118, 135, 145)
        else:
            color = PLAYER
        rect = self._rect(self.state.player.position, cell_px, offset).inflate(
            -max(0, cell_px // 4),
            -max(0, cell_px // 4),
        )
        pygame.draw.rect(surface, color, rect, border_radius=max(0, cell_px // 4))
        if cell_px >= 4:
            eye_x = rect.centerx + self.state.player.facing[0]
            eye_y = rect.centery + self.state.player.facing[1]
            surface.set_at((eye_x, eye_y), PLAYER_FACE)

    def _draw_phase_tint(
        self,
        surface: pygame.Surface,
        cell_px: int,
        offset: Coord,
    ) -> None:
        if self.state.phase == "playing":
            return
        board_rect = pygame.Rect(offset[0], offset[1], cell_px * GRID_SIZE, cell_px * GRID_SIZE)
        overlay = pygame.Surface(board_rect.size, pygame.SRCALPHA)
        color = CLEARED_TINT if self.state.phase == "cleared" else DEAD_TINT
        overlay.fill((*color, 72))
        surface.blit(overlay, board_rect)

    def _rect(self, cell: Coord, cell_px: int, offset: Coord) -> pygame.Rect:
        return pygame.Rect(
            offset[0] + cell[0] * cell_px,
            offset[1] + cell[1] * cell_px,
            cell_px,
            cell_px,
        )

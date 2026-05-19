from __future__ import annotations

import random
import time
from dataclasses import replace

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.input import GamepadButton
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

from .direct_gamepad import DirectGamepadSnapshot, DirectTetrisGamepads
from .state import (BOARD_HEIGHT, BOARD_WIDTH, CELL_SIZE_PX,
                    MOVE_REPEAT_DELAY_MS, MOVE_REPEAT_INTERVAL_MS,
                    PIECE_ROTATIONS, TetrisColor, TetrisControls,
                    TetrisGameState, TetrisInputMemory, TetrisPiece,
                    TetrisPieceKind, TetrisPlayerState, advance_player,
                    queue_garbage_for_opponents, restart_match,
                    update_match_end_state)

BACKGROUND_COLOR = pygame.Color(0, 8, 20)
PANEL_BACKGROUND_COLOR = pygame.Color(0, 18, 40)
HUD_PANEL_COLOR = pygame.Color(0, 3, 7)
BOARD_BACKGROUND_COLOR = pygame.Color(0, 0, 0)
BOARD_BORDER_COLOR = pygame.Color(40, 255, 226)
BOARD_BORDER_SHADOW_COLOR = pygame.Color(0, 78, 148)
GRID_COLOR = pygame.Color(24, 35, 45)
GHOST_COLOR = pygame.Color(88, 96, 118)
GARBAGE_WARNING_COLOR = pygame.Color(255, 70, 80)
GAME_OVER_COLOR = pygame.Color(255, 35, 60)
WIN_OVERLAY_COLOR = pygame.Color(255, 228, 68)
LOSE_OVERLAY_COLOR = pygame.Color(255, 58, 86)
RESTART_BUTTON_COLOR = pygame.Color(40, 255, 226)
PLAYER_ACCENT_COLORS = (
    pygame.Color(0, 220, 255),
    pygame.Color(255, 211, 64),
    pygame.Color(185, 112, 255),
    pygame.Color(74, 222, 128),
)
TETRIS_PALETTE: dict[TetrisColor, pygame.Color] = {
    TetrisColor.CYAN: pygame.Color(0, 238, 255),
    TetrisColor.YELLOW: pygame.Color(255, 225, 58),
    TetrisColor.PURPLE: pygame.Color(190, 104, 255),
    TetrisColor.GREEN: pygame.Color(72, 224, 119),
    TetrisColor.RED: pygame.Color(255, 75, 96),
    TetrisColor.BLUE: pygame.Color(83, 132, 255),
    TetrisColor.ORANGE: pygame.Color(255, 154, 56),
    TetrisColor.GARBAGE: pygame.Color(82, 88, 103),
}
RNG_NAMESPACE = "tetris"
PREVIEW_CELL_SIZE_PX = 2
NEXT_PREVIEW_COUNT = 6
logger = get_logger(__name__)


def _blend_color(
    color: pygame.Color,
    target: pygame.Color,
    amount: float,
) -> pygame.Color:
    return pygame.Color(
        int(color.r + ((target.r - color.r) * amount)),
        int(color.g + ((target.g - color.g) * amount)),
        int(color.b + ((target.b - color.b) * amount)),
    )


class TetrisRenderer(StatefulBaseRenderer[TetrisGameState]):
    def __init__(
        self,
        *,
        randomness: RandomnessProvider | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self._rng = rng or (randomness or RandomnessProvider()).rng(RNG_NAMESPACE)
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self._fonts: dict[int, pygame.font.Font] = {}
        self._last_logged_controls_by_player: dict[int, tuple[object, ...]] = {}
        self._gamepads = DirectTetrisGamepads()

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> TetrisGameState:
        del window, peripheral_manager, orientation
        return TetrisGameState.create(self._rng)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            raise RuntimeError("TetrisRenderer requires an initialized display surface")
        elapsed_ms = self._elapsed_ms(window)
        self._gamepads.refresh(player_count=len(self.state.players))
        controls_by_player: list[TetrisControls] = []
        for player_index, player in enumerate(self.state.players):
            snapshot = self._snapshot_for_player(player_index)
            controls = self._controls_for_snapshot(
                player.input_memory,
                snapshot,
                elapsed_ms,
            )
            self._log_renderer_command(player_index, snapshot, controls)
            controls_by_player.append(controls)
        if self.state.match_finished:
            if any(controls.restart for controls in controls_by_player):
                restart_match(self.state, self._rng)
        else:
            for player_index, player in enumerate(self.state.players):
                controls = replace(controls_by_player[player_index], restart=False)
                cleared = advance_player(player, controls, elapsed_ms, self._rng)
                queue_garbage_for_opponents(self.state, player_index, cleared)
            update_match_end_state(self.state)

        window.fill(BACKGROUND_COLOR)
        self._render_players(window.screen, orientation)

    def _elapsed_ms(self, window: DisplayContext) -> float:
        if window.clock is None:
            return 16.0
        elapsed = float(window.clock.get_time())
        if elapsed <= 0:
            return 16.0
        return min(elapsed, 100.0)

    def _snapshot_for_player(self, player_index: int) -> DirectGamepadSnapshot:
        return self._latest_snapshot(player_index)

    def _latest_snapshot(self, player_index: int) -> DirectGamepadSnapshot:
        return self._gamepads.snapshot_for_slot(player_index)

    def _internal_process(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._active_peripheral_manager = peripheral_manager
        super()._internal_process(window, peripheral_manager, orientation)

    def _controls_for_snapshot(
        self,
        memory: TetrisInputMemory,
        snapshot: DirectGamepadSnapshot,
        elapsed_ms: float,
    ) -> TetrisControls:
        move_direction = self._move_direction(snapshot)
        move_x = self._repeat_move(memory, move_direction, elapsed_ms)
        dpad_up = snapshot.dpad.y > 0 and memory.previous_dpad_y <= 0
        memory.previous_dpad_y = snapshot.dpad.y
        # NORTH is reserved for the global navigation alternate-activate exit.
        return TetrisControls(
            move_x=move_x,
            soft_drop=self._soft_drop(snapshot),
            hard_drop=snapshot.button_tapped(GamepadButton.SOUTH),
            rotate_cw=snapshot.button_tapped(GamepadButton.EAST),
            rotate_ccw=False,
            hold=dpad_up,
            restart=snapshot.button_tapped(GamepadButton.MINUS),
        )

    def _log_renderer_command(
        self,
        player_index: int,
        snapshot: DirectGamepadSnapshot,
        controls: TetrisControls,
    ) -> None:
        signature = self._control_signature(controls)
        previous = self._last_logged_controls_by_player.get(player_index)
        if signature == previous and controls.move_x == 0:
            return
        self._last_logged_controls_by_player[player_index] = signature
        if not signature:
            return
        logger.info(
            "tetris.command player=%s slot=%s age_ms=%.2f move_x=%s soft=%s hard=%s rotate_cw=%s rotate_ccw=%s hold=%s restart=%s",
            player_index,
            snapshot.slot,
            (time.monotonic() - snapshot.timestamp_monotonic) * 1000,
            controls.move_x,
            controls.soft_drop,
            controls.hard_drop,
            controls.rotate_cw,
            controls.rotate_ccw,
            controls.hold,
            controls.restart,
        )

    def _control_signature(self, controls: TetrisControls) -> tuple[object, ...]:
        if not (
            controls.move_x
            or controls.soft_drop
            or controls.hard_drop
            or controls.rotate_cw
            or controls.rotate_ccw
            or controls.hold
            or controls.restart
        ):
            return ()
        return (
            controls.move_x,
            controls.soft_drop,
            controls.hard_drop,
            controls.rotate_cw,
            controls.rotate_ccw,
            controls.hold,
            controls.restart,
        )

    def _move_direction(self, snapshot: DirectGamepadSnapshot) -> int:
        if snapshot.dpad.x != 0:
            return 1 if snapshot.dpad.x > 0 else -1
        return 0

    def _soft_drop(self, snapshot: DirectGamepadSnapshot) -> bool:
        return snapshot.dpad.y < 0

    def _repeat_move(
        self,
        memory: TetrisInputMemory,
        direction: int,
        elapsed_ms: float,
    ) -> int:
        if direction == 0:
            memory.previous_move_x = 0
            memory.held_move_x = 0
            memory.move_repeat_elapsed_ms = 0.0
            memory.move_repeat_primed = False
            return 0
        if direction != memory.held_move_x:
            memory.previous_move_x = direction
            memory.held_move_x = direction
            memory.move_repeat_elapsed_ms = 0.0
            memory.move_repeat_primed = False
            return direction
        memory.move_repeat_elapsed_ms += elapsed_ms
        threshold = (
            MOVE_REPEAT_INTERVAL_MS
            if memory.move_repeat_primed
            else MOVE_REPEAT_DELAY_MS
        )
        if memory.move_repeat_elapsed_ms < threshold:
            return 0
        memory.move_repeat_elapsed_ms = 0.0
        memory.move_repeat_primed = True
        return direction

    def _render_players(
        self,
        screen: pygame.Surface,
        orientation: Orientation,
    ) -> None:
        panel_width = screen.get_width() // orientation.layout.columns
        panel_height = screen.get_height() // orientation.layout.rows
        render_scale = max(1, min(panel_width // 64, panel_height // 64))
        for player_index, player in enumerate(self.state.players):
            col = player_index % orientation.layout.columns
            row = player_index // orientation.layout.columns
            panel = pygame.Rect(
                col * panel_width,
                row * panel_height,
                panel_width,
                panel_height,
            )
            self._render_player_panel(
                screen,
                panel,
                player,
                player_index,
                render_scale,
            )

    def _render_player_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        player_index: int,
        render_scale: int,
    ) -> None:
        pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel)
        accent = PLAYER_ACCENT_COLORS[player_index % len(PLAYER_ACCENT_COLORS)]
        cell_size = CELL_SIZE_PX * render_scale
        preview_cell_size = PREVIEW_CELL_SIZE_PX * render_scale
        board_width_px = BOARD_WIDTH * cell_size
        board_height_px = BOARD_HEIGHT * cell_size
        board_total_width = board_width_px + (2 * render_scale)
        board_total_height = board_height_px + (2 * render_scale)
        board_left = panel.left + ((panel.width - board_total_width) // 2) + render_scale
        board_top = (
            panel.top
            + max(render_scale, (panel.height - board_total_height) // 2)
            + render_scale
        )
        board_rect = pygame.Rect(
            board_left - render_scale,
            board_top - render_scale,
            board_width_px + (2 * render_scale),
            board_height_px + (2 * render_scale),
        )
        hold_rect = pygame.Rect(
            panel.left + render_scale,
            panel.top + render_scale,
            max(1, board_rect.left - panel.left - (3 * render_scale)),
            19 * render_scale,
        )
        garbage_rect = pygame.Rect(
            hold_rect.left,
            hold_rect.bottom + (2 * render_scale),
            hold_rect.width,
            max(1, panel.bottom - hold_rect.bottom - (3 * render_scale)),
        )
        next_rect = pygame.Rect(
            board_rect.right + (2 * render_scale),
            panel.top + render_scale,
            max(1, panel.right - board_rect.right - (3 * render_scale)),
            panel.height - (2 * render_scale),
        )
        self._draw_hud_frame(screen, hold_rect, accent, render_scale)
        self._draw_hud_frame(screen, garbage_rect, accent, render_scale)
        self._draw_hud_frame(screen, board_rect, accent, render_scale)
        self._draw_hud_frame(screen, next_rect, accent, render_scale)
        board_inner = board_rect.inflate(-2 * render_scale, -2 * render_scale)
        pygame.draw.rect(screen, BOARD_BACKGROUND_COLOR, board_inner)
        self._render_board(screen, board_left, board_top, player, cell_size)
        self._render_ghost(screen, board_left, board_top, player, cell_size)
        self._render_active_piece(screen, board_left, board_top, player, cell_size)
        self._render_hold_panel(
            screen,
            hold_rect,
            player,
            accent,
            render_scale,
            preview_cell_size,
        )
        self._render_next_panel(
            screen,
            next_rect,
            player,
            accent,
            render_scale,
            preview_cell_size,
        )
        self._render_garbage_meter(
            screen,
            garbage_rect,
            player,
            render_scale,
        )
        if player.game_over:
            self._render_game_over(screen, board_rect)
        if self.state.match_finished:
            self._render_match_result(screen, panel, board_rect, player_index, render_scale)

    def _draw_hud_frame(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        accent: pygame.Color,
        render_scale: int,
    ) -> None:
        pygame.draw.rect(screen, BOARD_BORDER_SHADOW_COLOR, rect)
        pygame.draw.rect(screen, BOARD_BORDER_COLOR, rect, render_scale)
        inner = rect.inflate(-2 * render_scale, -2 * render_scale)
        if inner.width <= 0 or inner.height <= 0:
            return
        pygame.draw.rect(screen, BOARD_BORDER_COLOR, inner, render_scale)
        content = inner.inflate(-2 * render_scale, -2 * render_scale)
        if content.width > 0 and content.height > 0:
            pygame.draw.rect(screen, HUD_PANEL_COLOR, content)
        pygame.draw.line(screen, accent, rect.topleft, rect.topright, render_scale)

    def _render_board(
        self,
        screen: pygame.Surface,
        board_left: int,
        board_top: int,
        player: TetrisPlayerState,
        cell_size: int,
    ) -> None:
        for y, row in enumerate(player.board):
            for x, color in enumerate(row):
                rect = self._cell_rect(board_left, board_top, x, y, cell_size)
                if color is None:
                    pygame.draw.rect(screen, GRID_COLOR, rect, 1)
                else:
                    self._draw_block(screen, rect, TETRIS_PALETTE[color])

    def _render_ghost(
        self,
        screen: pygame.Surface,
        board_left: int,
        board_top: int,
        player: TetrisPlayerState,
        cell_size: int,
    ) -> None:
        if player.active is None or player.game_over:
            return
        ghost = player.active
        while not self._piece_collides(player, ghost.moved(0, 1)):
            ghost = ghost.moved(0, 1)
        if ghost == player.active:
            return
        for x, y in ghost.cells():
            if y >= 0:
                pygame.draw.rect(
                    screen,
                    GHOST_COLOR,
                    self._cell_rect(board_left, board_top, x, y, cell_size),
                    max(1, cell_size // 3),
                )

    def _render_active_piece(
        self,
        screen: pygame.Surface,
        board_left: int,
        board_top: int,
        player: TetrisPlayerState,
        cell_size: int,
    ) -> None:
        if player.active is None:
            return
        color = TETRIS_PALETTE[player.active.color]
        for x, y in player.active.cells():
            if y >= 0:
                rect = self._cell_rect(board_left, board_top, x, y, cell_size)
                self._draw_block(screen, rect, color)

    def _render_hold_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        accent: pygame.Color,
        render_scale: int,
        preview_cell_size: int,
    ) -> None:
        self._render_mini_label(screen, "H", panel.centerx, panel.top, accent, render_scale)
        if player.hold_piece is not None:
            self._render_preview_piece(
                screen,
                player.hold_piece,
                panel.left + (2 * render_scale),
                panel.top + (7 * render_scale),
                cell_size=preview_cell_size,
                dim=player.hold_used,
            )

    def _render_next_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        accent: pygame.Color,
        render_scale: int,
        preview_cell_size: int,
    ) -> None:
        self._render_mini_label(screen, "N", panel.centerx, panel.top, accent, render_scale)
        preview_x = panel.left + (2 * render_scale)
        for index, kind in enumerate(list(player.next_queue)[:NEXT_PREVIEW_COUNT]):
            self._render_preview_piece(
                screen,
                kind,
                preview_x,
                panel.top + ((6 + (index * 9)) * render_scale),
                cell_size=preview_cell_size,
            )

    def _render_mini_label(
        self,
        screen: pygame.Surface,
        label: str,
        x: int,
        y: int,
        color: pygame.Color,
        render_scale: int,
    ) -> None:
        font = self._tiny_font(render_scale)
        surface = font.render(label, False, color)
        rect = surface.get_rect()
        rect.midtop = (x, y)
        screen.blit(surface, rect)

    def _render_preview_piece(
        self,
        screen: pygame.Surface,
        kind: TetrisPieceKind,
        x: int,
        y: int,
        *,
        cell_size: int,
        dim: bool = False,
    ) -> None:
        color = TETRIS_PALETTE[TetrisPiece(kind=kind).color]
        if dim:
            color = pygame.Color(color.r // 3, color.g // 3, color.b // 3)
        for cell_x, cell_y in PIECE_ROTATIONS[kind][0]:
            rect = pygame.Rect(
                x + (cell_x * cell_size),
                y + (cell_y * cell_size),
                cell_size,
                cell_size,
            )
            self._draw_block(screen, rect, color)

    def _render_garbage_meter(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        render_scale: int,
    ) -> None:
        fill_bottom = panel.bottom - (2 * render_scale)
        bar_height = 4 * render_scale
        for index in range(min(player.pending_garbage, 9)):
            rect = pygame.Rect(
                panel.left + (2 * render_scale),
                fill_bottom - ((index + 1) * bar_height),
                max(1, panel.width - (4 * render_scale)),
                max(1, bar_height - render_scale),
            )
            pygame.draw.rect(screen, GARBAGE_WARNING_COLOR, rect)

    def _draw_block(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        color: pygame.Color,
    ) -> None:
        pygame.draw.rect(screen, color, rect)
        if rect.width <= 1 or rect.height <= 1:
            return
        highlight = _blend_color(color, pygame.Color("white"), 0.44)
        lowlight = _blend_color(color, pygame.Color("black"), 0.38)
        bevel = max(1, min(rect.width, rect.height) // 3)
        pygame.draw.rect(screen, highlight, pygame.Rect(rect.left, rect.top, rect.width, bevel))
        pygame.draw.rect(screen, highlight, pygame.Rect(rect.left, rect.top, bevel, rect.height))
        pygame.draw.rect(
            screen,
            lowlight,
            pygame.Rect(rect.left, rect.bottom - bevel, rect.width, bevel),
        )
        pygame.draw.rect(
            screen,
            lowlight,
            pygame.Rect(rect.right - bevel, rect.top, bevel, rect.height),
        )
        inset = max(1, bevel)
        inner = rect.inflate(-2 * inset, -2 * inset)
        if inner.width > 0 and inner.height > 0:
            pygame.draw.rect(screen, _blend_color(color, pygame.Color("white"), 0.12), inner)

    def _render_game_over(
        self,
        screen: pygame.Surface,
        board_rect: pygame.Rect,
    ) -> None:
        overlay = pygame.Surface(board_rect.size, pygame.SRCALPHA)
        overlay.fill((30, 0, 8, 180))
        screen.blit(overlay, board_rect.topleft)
        pygame.draw.line(
            screen,
            GAME_OVER_COLOR,
            board_rect.topleft,
            board_rect.bottomright,
            2,
        )
        pygame.draw.line(
            screen,
            GAME_OVER_COLOR,
            board_rect.topright,
            board_rect.bottomleft,
            2,
        )

    def _render_match_result(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        board_rect: pygame.Rect,
        player_index: int,
        render_scale: int,
    ) -> None:
        won = self.state.winner_index == player_index
        overlay = pygame.Surface(panel.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, panel.topleft)

        card_width = min(panel.width - (6 * render_scale), board_rect.width + (12 * render_scale))
        card_height = min(panel.height - (8 * render_scale), 28 * render_scale)
        card = pygame.Rect(0, 0, max(1, card_width), max(1, card_height))
        card.center = board_rect.center
        pygame.draw.rect(screen, pygame.Color(0, 5, 12), card)
        pygame.draw.rect(screen, BOARD_BORDER_SHADOW_COLOR, card, max(1, render_scale))
        pygame.draw.rect(screen, RESTART_BUTTON_COLOR, card.inflate(-2 * render_scale, -2 * render_scale), max(1, render_scale))

        label = "WIN" if won else "LOSE"
        label_color = WIN_OVERLAY_COLOR if won else LOSE_OVERLAY_COLOR
        label_font = self._font(max(13, 9 * render_scale))
        label_surface = label_font.render(label, False, label_color)
        label_rect = label_surface.get_rect()
        label_rect.midtop = (card.centerx, card.top + (4 * render_scale))
        screen.blit(label_surface, label_rect)

        restart_font = self._font(max(8, 5 * render_scale))
        restart_surface = restart_font.render("PRESS -", False, RESTART_BUTTON_COLOR)
        restart_rect = restart_surface.get_rect()
        restart_rect.midtop = (card.centerx, label_rect.bottom + (2 * render_scale))
        screen.blit(restart_surface, restart_rect)

        reset_surface = restart_font.render("RESTART", False, pygame.Color("white"))
        reset_rect = reset_surface.get_rect()
        reset_rect.midtop = (card.centerx, restart_rect.bottom)
        screen.blit(reset_surface, reset_rect)

    def _cell_rect(
        self,
        board_left: int,
        board_top: int,
        x: int,
        y: int,
        cell_size: int,
    ) -> pygame.Rect:
        return pygame.Rect(
            board_left + x * cell_size,
            board_top + y * cell_size,
            cell_size,
            cell_size,
        )

    def _piece_collides(
        self,
        player: TetrisPlayerState,
        piece: TetrisPiece,
    ) -> bool:
        for x, y in piece.cells():
            if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
                return True
            if y >= 0 and player.board[y][x] is not None:
                return True
        return False

    def _tiny_font(self, render_scale: int) -> pygame.font.Font:
        return self._font(max(8, 6 * render_scale))

    def _font(self, font_size: int) -> pygame.font.Font:
        if font_size not in self._fonts:
            if not pygame.font.get_init():
                pygame.font.init()
            self._fonts[font_size] = pygame.font.Font(None, font_size)
        return self._fonts[font_size]

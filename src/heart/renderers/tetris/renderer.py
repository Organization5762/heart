from __future__ import annotations

import random
import time
from dataclasses import replace
from enum import StrEnum

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
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
                    PIECE_ROTATIONS, PLAYER_COUNT, TetrisColor, TetrisControls,
                    TetrisGameState, TetrisInputMemory, TetrisPiece,
                    TetrisPieceKind, TetrisPlayerState, advance_player,
                    collides, queue_garbage_for_opponents,
                    update_match_end_state)

BACKGROUND_COLOR = pygame.Color(0, 8, 20)
PANEL_BACKGROUND_COLOR = pygame.Color(0, 18, 40)
HUD_PANEL_COLOR = pygame.Color(0, 3, 7)
BOARD_BACKGROUND_COLOR = pygame.Color(0, 0, 0)
BOARD_BORDER_COLOR = pygame.Color(40, 255, 226)
BOARD_BORDER_SHADOW_COLOR = pygame.Color(0, 78, 148)
GHOST_PIECE_COLOR = pygame.Color(96, 108, 132)
MODE_LABEL_COLOR = pygame.Color(255, 255, 255)
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
PIXEL_FONT_PATH = "Grand9K Pixel.ttf"
PREVIEW_CELL_SIZE_PX = 2
NEXT_PREVIEW_COUNT = 6
DUAL_SYNCED_PLAYER_COUNT = 2
SOLO_MIRRORED_PLAYER_COUNT = 1
logger = get_logger(__name__)


class TetrisPlayMode(StrEnum):
    FOUR_PLAYER = "four_player"
    DUAL_SYNCED = "dual_synced"
    SOLO_MIRRORED = "solo_mirrored"


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
        self._native_surface: pygame.Surface | None = None
        self._play_mode = TetrisPlayMode.FOUR_PLAYER
        self._mode_switch_chord_held = False
        self._synchronized_input_memory = TetrisInputMemory()

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> TetrisGameState:
        del window, peripheral_manager, orientation
        return self._create_game_state()

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        if window.screen is None:
            raise RuntimeError("TetrisRenderer requires an initialized display surface")
        elapsed_ms = self._elapsed_ms(window)
        self._gamepads.refresh(player_count=PLAYER_COUNT)
        snapshots = [self._latest_snapshot(slot) for slot in range(PLAYER_COUNT)]
        if self._consume_mode_switch_chord(snapshots):
            self._switch_play_mode()
            controls_by_player = [TetrisControls() for _player in self.state.players]
        else:
            controls_by_player = self._controls_by_player(snapshots, elapsed_ms)
        if self.state.match_finished:
            if any(controls.restart for controls in controls_by_player):
                self._reset_current_game()
        else:
            for player_index, player in enumerate(self.state.players):
                controls = replace(controls_by_player[player_index], restart=False)
                cleared = advance_player(player, controls, elapsed_ms, self._rng)
                if self._play_mode is TetrisPlayMode.FOUR_PLAYER:
                    queue_garbage_for_opponents(self.state, player_index, cleared)
            if self._play_mode is TetrisPlayMode.FOUR_PLAYER:
                update_match_end_state(self.state)

        render_target = self._native_render_target(window)
        render_target.fill((0, 0, 0, 0))
        pygame.draw.rect(
            render_target,
            BACKGROUND_COLOR,
            pygame.Rect((0, 0), window.device.full_display_size()),
        )
        self._render_players(
            render_target,
            window.device.individual_display_size(),
            orientation.layout.columns,
            orientation.layout.rows,
        )
        if render_target is not window.screen:
            pygame.transform.scale(
                render_target, window.screen.get_size(), window.screen
            )

    def _native_render_target(self, window: DisplayContext) -> pygame.Surface:
        if window.screen is None:
            raise RuntimeError("TetrisRenderer requires an initialized display surface")
        native_size = window.device.full_display_size()
        if window.screen.get_size() == native_size:
            return window.screen
        if (
            self._native_surface is None
            or self._native_surface.get_size() != native_size
        ):
            self._native_surface = pygame.Surface(native_size, pygame.SRCALPHA)
        return self._native_surface

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

    def _create_game_state(self) -> TetrisGameState:
        return TetrisGameState.create(
            self._rng,
            player_count=self._player_count_for_mode(),
        )

    def _player_count_for_mode(self) -> int:
        if self._play_mode is TetrisPlayMode.DUAL_SYNCED:
            return DUAL_SYNCED_PLAYER_COUNT
        if self._play_mode is TetrisPlayMode.SOLO_MIRRORED:
            return SOLO_MIRRORED_PLAYER_COUNT
        return PLAYER_COUNT

    def _controls_by_player(
        self,
        snapshots: list[DirectGamepadSnapshot],
        elapsed_ms: float,
    ) -> list[TetrisControls]:
        if self._uses_synchronized_controls():
            controls = self._controls_for_snapshots(
                self._synchronized_input_memory,
                snapshots,
                elapsed_ms,
            )
            self._log_renderer_command(
                0,
                self._command_source_snapshot(snapshots),
                controls,
            )
            return [controls for _player in self.state.players]

        controls_by_player: list[TetrisControls] = []
        for player_index, player in enumerate(self.state.players):
            snapshot = snapshots[player_index]
            controls = self._controls_for_snapshot(
                player.input_memory,
                snapshot,
                elapsed_ms,
            )
            self._log_renderer_command(player_index, snapshot, controls)
            controls_by_player.append(controls)
        return controls_by_player

    def _uses_synchronized_controls(self) -> bool:
        return self._play_mode in {
            TetrisPlayMode.DUAL_SYNCED,
            TetrisPlayMode.SOLO_MIRRORED,
        }

    def _consume_mode_switch_chord(
        self,
        snapshots: list[DirectGamepadSnapshot],
    ) -> bool:
        chord_held = any(
            snapshot.button_held(GamepadButton.PLUS)
            and snapshot.button_held(GamepadButton.MINUS)
            for snapshot in snapshots
        )
        should_switch = chord_held and not self._mode_switch_chord_held
        self._mode_switch_chord_held = chord_held
        return should_switch

    def _switch_play_mode(self) -> None:
        play_modes = tuple(TetrisPlayMode)
        next_index = (play_modes.index(self._play_mode) + 1) % len(play_modes)
        self._play_mode = play_modes[next_index]
        self._reset_current_game()

    def _reset_current_game(self) -> None:
        self.set_state(self._create_game_state())
        self._synchronized_input_memory = TetrisInputMemory()
        self._last_logged_controls_by_player.clear()

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
        return self._controls_for_snapshots(memory, [snapshot], elapsed_ms)

    def _controls_for_snapshots(
        self,
        memory: TetrisInputMemory,
        snapshots: list[DirectGamepadSnapshot],
        elapsed_ms: float,
    ) -> TetrisControls:
        move_direction = self._move_direction_for_snapshots(snapshots)
        move_x = self._repeat_move(memory, move_direction, elapsed_ms)
        dpad_y = self._dpad_y(snapshots)
        dpad_up = dpad_y > 0 and memory.previous_dpad_y <= 0
        memory.previous_dpad_y = dpad_y
        # NORTH is reserved for the global navigation alternate-activate exit.
        return TetrisControls(
            move_x=move_x,
            soft_drop=dpad_y < 0,
            hard_drop=self._button_tapped(snapshots, GamepadButton.SOUTH),
            rotate_cw=self._button_tapped(snapshots, GamepadButton.EAST),
            rotate_ccw=False,
            hold=dpad_up,
            restart=self._button_tapped(snapshots, GamepadButton.MINUS),
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
        return self._move_direction_for_snapshots([snapshot])

    def _move_direction_for_snapshots(
        self,
        snapshots: list[DirectGamepadSnapshot],
    ) -> int:
        for snapshot in snapshots:
            if snapshot.dpad.x != 0:
                return 1 if snapshot.dpad.x > 0 else -1
        return 0

    def _dpad_y(self, snapshots: list[DirectGamepadSnapshot]) -> int:
        for snapshot in snapshots:
            if snapshot.dpad.y != 0:
                return 1 if snapshot.dpad.y > 0 else -1
        return 0

    def _button_tapped(
        self,
        snapshots: list[DirectGamepadSnapshot],
        button: GamepadButton,
    ) -> bool:
        return any(snapshot.button_tapped(button) for snapshot in snapshots)

    def _command_source_snapshot(
        self,
        snapshots: list[DirectGamepadSnapshot],
    ) -> DirectGamepadSnapshot:
        for snapshot in snapshots:
            if snapshot.dpad.x != 0 or snapshot.dpad.y != 0 or snapshot.tapped_buttons:
                return snapshot
        for snapshot in snapshots:
            if snapshot.connected:
                return snapshot
        return snapshots[0]

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
        panel_size: tuple[int, int],
        panel_columns: int,
        panel_rows: int,
    ) -> None:
        panel_width, panel_height = panel_size
        columns = max(1, panel_columns)
        rows = max(1, panel_rows)
        for panel_index in range(columns * rows):
            player_index = self._player_index_for_panel(panel_index, columns * rows)
            if player_index >= len(self.state.players):
                continue
            player = self.state.players[player_index]
            col = panel_index % columns
            row = panel_index // columns
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
            )

    def _player_index_for_panel(self, panel_index: int, panel_count: int) -> int:
        if self._play_mode is TetrisPlayMode.SOLO_MIRRORED:
            return 0
        if self._play_mode is TetrisPlayMode.DUAL_SYNCED:
            if panel_count >= DUAL_SYNCED_PLAYER_COUNT * 2:
                return min(panel_index // 2, DUAL_SYNCED_PLAYER_COUNT - 1)
            return panel_index % DUAL_SYNCED_PLAYER_COUNT
        return panel_index

    def _render_player_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        player_index: int,
    ) -> None:
        pygame.draw.rect(screen, PANEL_BACKGROUND_COLOR, panel)
        accent = PLAYER_ACCENT_COLORS[player_index % len(PLAYER_ACCENT_COLORS)]
        cell_size = CELL_SIZE_PX
        preview_cell_size = PREVIEW_CELL_SIZE_PX
        board_width_px = BOARD_WIDTH * cell_size
        board_height_px = BOARD_HEIGHT * cell_size
        board_total_width = board_width_px + 2
        board_total_height = board_height_px + 2
        board_left = panel.left + ((panel.width - board_total_width) // 2) + 1
        board_top = panel.top + max(1, (panel.height - board_total_height) // 2) + 1
        board_rect = pygame.Rect(
            board_left - 1,
            board_top - 1,
            board_width_px + 2,
            board_height_px + 2,
        )
        hold_rect = pygame.Rect(
            panel.left + 1,
            panel.top + 1,
            max(1, board_rect.left - panel.left - 3),
            19,
        )
        garbage_rect = pygame.Rect(
            hold_rect.left,
            hold_rect.bottom + 2,
            hold_rect.width,
            max(1, panel.bottom - hold_rect.bottom - 3),
        )
        next_rect = pygame.Rect(
            board_rect.right + 2,
            panel.top + 1,
            max(1, panel.right - board_rect.right - 3),
            panel.height - 2,
        )
        self._draw_hud_frame(screen, hold_rect, accent)
        self._draw_hud_frame(screen, garbage_rect, accent)
        self._draw_hud_frame(screen, board_rect, accent)
        self._draw_hud_frame(screen, next_rect, accent)
        board_inner = board_rect.inflate(-2, -2)
        pygame.draw.rect(screen, BOARD_BACKGROUND_COLOR, board_inner)
        self._render_board(screen, board_left, board_top, player, cell_size)
        self._render_ghost_piece(screen, board_left, board_top, player, cell_size)
        self._render_active_piece(screen, board_left, board_top, player, cell_size)
        self._render_hold_panel(
            screen,
            hold_rect,
            player,
            accent,
            preview_cell_size,
        )
        self._render_next_panel(
            screen,
            next_rect,
            player,
            accent,
            preview_cell_size,
        )
        self._render_garbage_meter(
            screen,
            garbage_rect,
            player,
        )
        if player.game_over:
            self._render_game_over(screen, board_rect)
        if self.state.match_finished:
            self._render_match_result(screen, panel, board_rect, player_index)
        self._render_mode_label(screen, panel)

    def _render_mode_label(self, screen: pygame.Surface, panel: pygame.Rect) -> None:
        label = self._mode_label()
        label_surface = self._font(7).render(label, False, MODE_LABEL_COLOR)
        screen.blit(
            label_surface,
            (
                panel.left + 2,
                panel.bottom - label_surface.get_height() - 1,
            ),
        )

    def _mode_label(self) -> str:
        if self._play_mode is TetrisPlayMode.FOUR_PLAYER:
            return "F"
        if self._play_mode is TetrisPlayMode.DUAL_SYNCED:
            return "D"
        return "S"

    def _draw_hud_frame(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        accent: pygame.Color,
    ) -> None:
        pygame.draw.rect(screen, BOARD_BORDER_SHADOW_COLOR, rect)
        pygame.draw.rect(screen, BOARD_BORDER_COLOR, rect, 1)
        inner = rect.inflate(-2, -2)
        if inner.width <= 0 or inner.height <= 0:
            return
        pygame.draw.rect(screen, BOARD_BORDER_COLOR, inner, 1)
        content = inner.inflate(-2, -2)
        if content.width > 0 and content.height > 0:
            pygame.draw.rect(screen, HUD_PANEL_COLOR, content)
        pygame.draw.line(screen, accent, rect.topleft, rect.topright, 1)

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
                if color is not None:
                    rect = self._cell_rect(board_left, board_top, x, y, cell_size)
                    self._draw_block(screen, rect, TETRIS_PALETTE[color])

    def _render_ghost_piece(
        self,
        screen: pygame.Surface,
        board_left: int,
        board_top: int,
        player: TetrisPlayerState,
        cell_size: int,
    ) -> None:
        ghost = self._landing_piece(player)
        if ghost is None or ghost == player.active:
            return
        for x, y in ghost.cells():
            if y >= 0:
                rect = self._cell_rect(board_left, board_top, x, y, cell_size)
                pygame.draw.rect(screen, GHOST_PIECE_COLOR, rect, 1)

    def _landing_piece(self, player: TetrisPlayerState) -> TetrisPiece | None:
        if player.active is None or player.game_over:
            return None
        ghost = player.active
        while not collides(player.board, ghost.moved(0, 1)):
            ghost = ghost.moved(0, 1)
        return ghost

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
        preview_cell_size: int,
    ) -> None:
        del accent
        if player.hold_piece is not None:
            self._render_preview_piece(
                screen,
                player.hold_piece,
                panel.left + 2,
                panel.top + 7,
                cell_size=preview_cell_size,
                dim=player.hold_used,
            )

    def _render_next_panel(
        self,
        screen: pygame.Surface,
        panel: pygame.Rect,
        player: TetrisPlayerState,
        accent: pygame.Color,
        preview_cell_size: int,
    ) -> None:
        del accent
        preview_x = panel.left + 2
        for index, kind in enumerate(list(player.next_queue)[:NEXT_PREVIEW_COUNT]):
            self._render_preview_piece(
                screen,
                kind,
                preview_x,
                panel.top + 6 + (index * 9),
                cell_size=preview_cell_size,
            )

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
    ) -> None:
        fill_bottom = panel.bottom - 2
        bar_height = 4
        for index in range(min(player.pending_garbage, 9)):
            rect = pygame.Rect(
                panel.left + 2,
                fill_bottom - ((index + 1) * bar_height),
                max(1, panel.width - 4),
                max(1, bar_height - 1),
            )
            pygame.draw.rect(screen, GARBAGE_WARNING_COLOR, rect)

    def _draw_block(
        self,
        screen: pygame.Surface,
        rect: pygame.Rect,
        color: pygame.Color,
    ) -> None:
        pygame.draw.rect(screen, color, rect)

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
    ) -> None:
        won = self.state.winner_index == player_index
        overlay = pygame.Surface(panel.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        screen.blit(overlay, panel.topleft)

        card_width = min(panel.width - 4, board_rect.width + 16)
        card_height = min(panel.height - 8, 44)
        card = pygame.Rect(0, 0, max(1, card_width), max(1, card_height))
        card.center = board_rect.center
        pygame.draw.rect(screen, pygame.Color(0, 5, 12), card)
        pygame.draw.rect(screen, BOARD_BORDER_SHADOW_COLOR, card, 1)
        pygame.draw.rect(screen, RESTART_BUTTON_COLOR, card.inflate(-2, -2), 1)

        label = "WIN" if won else "LOSE"
        label_color = WIN_OVERLAY_COLOR if won else LOSE_OVERLAY_COLOR
        self._render_centered_result_text(
            screen,
            card.inflate(-6, -6),
            label=label,
            label_color=label_color,
        )

    def _render_centered_result_text(
        self,
        screen: pygame.Surface,
        bounds: pygame.Rect,
        *,
        label: str,
        label_color: pygame.Color,
    ) -> None:
        surfaces, gaps = self._fit_result_text_surfaces(
            bounds,
            label=label,
            label_color=label_color,
        )
        total_height = sum(surface.get_height() for surface in surfaces) + sum(gaps)
        y = bounds.centery - total_height // 2
        for surface, gap_after in zip(surfaces, [*gaps, 0]):
            rect = surface.get_rect()
            rect.midtop = (bounds.centerx, y)
            screen.blit(surface, rect)
            y = rect.bottom + gap_after

    def _fit_result_text_surfaces(
        self,
        bounds: pygame.Rect,
        *,
        label: str,
        label_color: pygame.Color,
    ) -> tuple[tuple[pygame.Surface, pygame.Surface, pygame.Surface], tuple[int, int]]:
        label_size = 12
        restart_size = 7
        while label_size >= 7 and restart_size >= 5:
            label_surface = self._font(label_size).render(label, False, label_color)
            restart_font = self._font(restart_size)
            press_surface = restart_font.render(
                "PRESS -",
                False,
                RESTART_BUTTON_COLOR,
            )
            reset_surface = restart_font.render("RESTART", False, pygame.Color("white"))
            surfaces = (label_surface, press_surface, reset_surface)
            gaps = (2, 0)
            total_height = sum(surface.get_height() for surface in surfaces) + sum(gaps)
            widest = max(surface.get_width() for surface in surfaces)
            if total_height <= bounds.height and widest <= bounds.width:
                return surfaces, gaps
            label_size -= 1
            restart_size -= 1
        return (
            (
                self._font(label_size).render(label, False, label_color),
                self._font(restart_size).render(
                    "PRESS -",
                    False,
                    RESTART_BUTTON_COLOR,
                ),
                self._font(restart_size).render(
                    "RESTART", False, pygame.Color("white")
                ),
            ),
            (1, 0),
        )

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

    def _font(self, font_size: int) -> pygame.font.Font:
        if font_size not in self._fonts:
            if not pygame.font.get_init():
                pygame.font.init()
            self._fonts[font_size] = Loader.load_font(PIXEL_FONT_PATH, font_size)
        return self._fonts[font_size]

from __future__ import annotations

import random

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.peripheral.core.input import GamepadButton, GamepadDpadValue
from heart.renderers.tetris import TetrisRenderer
from heart.renderers.tetris.direct_gamepad import DirectGamepadSnapshot
from heart.renderers.tetris.renderer import BOARD_BORDER_COLOR
from heart.renderers.tetris.state import (BOARD_WIDTH, TetrisControls,
                                          TetrisInputMemory,
                                          TetrisGameState, TetrisPiece,
                                          TetrisPieceKind, advance_player,
                                          restart_match,
                                          queue_garbage_for_opponents,
                                          update_match_end_state)
from heart.runtime.display_context import DisplayContext


class TestTetrisRules:
    def test_line_clear_queues_garbage_for_all_live_opponents(self) -> None:
        rng = random.Random(1)
        state = TetrisGameState.create(rng)
        player = state.players[0]
        player.board[-1] = [player.active.color if player.active else None] * BOARD_WIDTH
        for x in range(4):
            player.board[-1][x] = None
        player.active = TetrisPiece(TetrisPieceKind.I_PIECE, rotation=0, x=0, y=18)

        cleared = advance_player(
            player,
            TetrisControls(hard_drop=True),
            elapsed_ms=16,
            rng=rng,
        )
        queue_garbage_for_opponents(state, sender_index=0, line_count=cleared)

        assert cleared == 1
        assert [opponent.pending_garbage for opponent in state.players[1:]] == [1, 1, 1]

    def test_hold_stashes_current_piece_and_blocks_repeat_hold_until_lock(self) -> None:
        rng = random.Random(2)
        player = TetrisGameState.create(rng).players[0]
        first_kind = player.active.kind if player.active else None

        advance_player(player, TetrisControls(hold=True), elapsed_ms=16, rng=rng)
        held_after_first = player.hold_piece
        active_after_first = player.active.kind if player.active else None
        advance_player(player, TetrisControls(hold=True), elapsed_ms=16, rng=rng)

        assert held_after_first == first_kind
        assert player.hold_piece == held_after_first
        assert player.active is not None
        assert player.active.kind == active_after_first

    def test_match_finishes_when_only_one_player_is_alive(self) -> None:
        state = TetrisGameState.create(random.Random(3))
        for player in state.players[:3]:
            player.game_over = True

        update_match_end_state(state)

        assert state.match_finished
        assert state.winner_index == 3

    def test_match_restart_resets_all_players(self) -> None:
        rng = random.Random(4)
        state = TetrisGameState.create(rng)
        for player in state.players[:3]:
            player.game_over = True
        update_match_end_state(state)

        restart_match(state, rng)

        assert not state.match_finished
        assert state.winner_index is None
        assert all(not player.game_over for player in state.players)

    def test_soft_drop_moves_at_most_one_row_per_frame(self) -> None:
        rng = random.Random(5)
        player = TetrisGameState.create(rng).players[0]
        assert player.active is not None
        start_y = player.active.y

        advance_player(player, TetrisControls(soft_drop=True), elapsed_ms=1000, rng=rng)

        assert player.active is not None
        assert player.active.y == start_y + 1


class TestTetrisRenderer:
    def test_renderer_uses_full_display_mode(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))

        assert renderer.device_display_mode is DeviceDisplayMode.FULL

    def test_real_process_draws_four_player_panels(
        self,
        device: Device,
    ) -> None:
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = TetrisRenderer(rng=random.Random(1))
        renderer.set_state(TetrisGameState.create(random.Random(1)))
        renderer.initialized = True

        renderer.real_process(window, device.orientation)

        assert window.screen.get_at((16, 2))[:3] == BOARD_BORDER_COLOR[:3]
        assert window.screen.get_at((80, 2))[:3] == BOARD_BORDER_COLOR[:3]
        assert window.screen.get_at((144, 2))[:3] == BOARD_BORDER_COLOR[:3]
        assert window.screen.get_at((208, 2))[:3] == BOARD_BORDER_COLOR[:3]

    def test_controller_mapping_uses_requested_buttons(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        controls = renderer._controls_for_snapshot(
            TetrisInputMemory(),
            DirectGamepadSnapshot(
                connected=True,
                identifier="test",
                tapped_buttons=frozenset({GamepadButton.EAST, GamepadButton.SOUTH}),
                dpad=GamepadDpadValue(y=1),
            ),
            elapsed_ms=16,
        )

        assert controls.rotate_cw is True
        assert controls.hard_drop is True
        assert controls.hold is True
        assert controls.rotate_ccw is False

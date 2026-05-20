from __future__ import annotations

import random

import pygame

from heart.device import Device, Rectangle
from heart.peripheral.core.input import GamepadButton, GamepadDpadValue
from heart.renderers.tetris.direct_gamepad import DirectGamepadSnapshot
from heart.renderers.tetris.renderer import (
    BOARD_BORDER_COLOR,
    GHOST_PIECE_COLOR,
    TetrisPlayMode,
    TetrisRenderer,
)
from heart.renderers.tetris.state import (
    BOARD_WIDTH,
    TetrisControls,
    TetrisGameState,
    TetrisInputMemory,
    TetrisPiece,
    TetrisPieceKind,
    advance_player,
    queue_garbage_for_opponents,
)
from heart.runtime.display_context import DisplayContext


class TestTetrisRules:
    def test_line_clear_queues_garbage_for_all_live_opponents(self) -> None:
        rng = random.Random(1)
        state = TetrisGameState.create(rng)
        player = state.players[0]
        player.board[-1] = [
            player.active.color if player.active else None
        ] * BOARD_WIDTH
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
        assert [opponent.pending_garbage for opponent in state.players[1:]] == [
            1,
            1,
            1,
        ]


class TestTetrisRenderer:
    def test_plus_minus_chord_switches_mode_once_until_released(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        chord = [
            DirectGamepadSnapshot(
                connected=True,
                identifier="test",
                buttons={GamepadButton.PLUS: True, GamepadButton.MINUS: True},
                slot=0,
            )
        ]
        released = [DirectGamepadSnapshot(connected=True, identifier="test", slot=0)]

        assert renderer._consume_mode_switch_chord(chord) is True
        assert renderer._consume_mode_switch_chord(chord) is False
        assert renderer._consume_mode_switch_chord(released) is False
        assert renderer._consume_mode_switch_chord(chord) is True

    def test_switch_play_mode_resets_to_two_synced_boards(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        renderer.set_state(TetrisGameState.create(random.Random(2)))
        renderer.state.players[0].score = 900

        renderer._switch_play_mode()

        assert renderer._play_mode is TetrisPlayMode.SOLO_SYNCED
        assert len(renderer.state.players) == 2
        assert all(player.score == 0 for player in renderer.state.players)
        assert renderer.state.players[0].active is not None
        assert renderer.state.players[1].active is not None
        assert (
            renderer.state.players[0].active.kind
            != renderer.state.players[1].active.kind
        )

    def test_solo_mode_applies_any_controller_to_both_boards(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        renderer._play_mode = TetrisPlayMode.SOLO_SYNCED
        renderer.set_state(TetrisGameState.create(random.Random(1), player_count=2))
        snapshots = [
            DirectGamepadSnapshot(connected=False, identifier=None, slot=0),
            DirectGamepadSnapshot(connected=False, identifier=None, slot=1),
            DirectGamepadSnapshot(connected=False, identifier=None, slot=2),
            DirectGamepadSnapshot(
                connected=True,
                identifier="test",
                tapped_buttons=frozenset({GamepadButton.EAST}),
                dpad=GamepadDpadValue(x=-1),
                slot=3,
            ),
        ]

        controls = renderer._controls_by_player(snapshots, elapsed_ms=16)

        assert controls == [
            TetrisControls(move_x=-1, rotate_cw=True),
            TetrisControls(move_x=-1, rotate_cw=True),
        ]

    def test_north_button_is_reserved_for_navigation_exit(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        controls = renderer._controls_for_snapshot(
            TetrisInputMemory(),
            DirectGamepadSnapshot(
                connected=True,
                identifier="test",
                tapped_buttons=frozenset({GamepadButton.NORTH}),
            ),
            elapsed_ms=16,
        )

        assert controls == TetrisControls()

    def test_landing_piece_projects_to_bottom(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        player = TetrisGameState.create(random.Random(1), player_count=1).players[0]
        player.active = TetrisPiece(TetrisPieceKind.I_PIECE, rotation=0, x=0, y=0)

        ghost = renderer._landing_piece(player)

        assert ghost == TetrisPiece(TetrisPieceKind.I_PIECE, rotation=0, x=0, y=18)

    def test_render_ghost_piece_draws_bottom_shade(self) -> None:
        renderer = TetrisRenderer(rng=random.Random(1))
        player = TetrisGameState.create(random.Random(1), player_count=1).players[0]
        player.active = TetrisPiece(TetrisPieceKind.I_PIECE, rotation=0, x=0, y=0)
        surface = pygame.Surface((64, 64))

        renderer._render_ghost_piece(surface, 0, 0, player, 3)

        assert surface.get_at((0, 57))[:3] == GHOST_PIECE_COLOR[:3]

    def test_solo_mode_draws_two_screen_panels(self, device: Device) -> None:
        device.orientation = Rectangle.with_layout(columns=2, rows=1)
        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = TetrisRenderer(rng=random.Random(1))
        renderer._play_mode = TetrisPlayMode.SOLO_SYNCED
        renderer.set_state(TetrisGameState.create(random.Random(1), player_count=2))
        renderer.initialized = True

        renderer.real_process(window, device.orientation)

        assert window.screen.get_at((16, 2))[:3] == BOARD_BORDER_COLOR[:3]
        assert window.screen.get_at((80, 2))[:3] == BOARD_BORDER_COLOR[:3]

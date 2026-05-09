import random
from dataclasses import replace

import pygame

from heart.device import Rectangle
from heart.peripheral.core.input import (FrameTick, GamepadDpadValue,
                                         GamepadSnapshot, KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.bomberman import BombermanRenderer
from heart.renderers.bomberman.state import (BOMB_FUSE_MS, BombermanBomb,
                                             BombermanInput, BombermanPlayer,
                                             BombermanState,
                                             advance_bomberman_state,
                                             create_initial_bomberman_state,
                                             input_from_snapshots)
from heart.runtime.display_context import DisplayContext


def _frame(delta_ms: float) -> FrameTick:
    return FrameTick(
        frame_index=0,
        delta_ms=delta_ms,
        delta_s=delta_ms / 1000.0,
        monotonic_s=0.0,
    )


class TestBombermanState:
    def test_player_moves_on_open_grid_and_respects_walls(self) -> None:
        state = create_initial_bomberman_state(
            rng=random.Random(1),
            soft_block_density=0.0,
        )
        state = replace(state, soft_blocks=frozenset({(14, 14)}))

        moved = advance_bomberman_state(
            state,
            _frame(16.0),
            BombermanInput(movement=(1, 0)),
        )
        assert moved.player.position == (2, 1)
        assert moved.player.facing == (1, 0)

        blocked = advance_bomberman_state(
            moved,
            _frame(200.0),
            BombermanInput(movement=(0, 1)),
        )
        assert blocked.player.position == (2, 1)
        assert blocked.player.facing == (0, 1)

    def test_bomb_explosion_clears_soft_blocks_until_wall(self) -> None:
        walls = frozenset({(0, 1), (4, 1)})
        state = BombermanState(
            player=BombermanPlayer(position=(1, 1)),
            walls=walls,
            soft_blocks=frozenset({(2, 1), (3, 1)}),
            bombs=(BombermanBomb(position=(1, 1), remaining_ms=1.0),),
        )

        next_state = advance_bomberman_state(
            state,
            _frame(2.0),
            BombermanInput(),
        )

        assert (2, 1) not in next_state.soft_blocks
        assert (3, 1) in next_state.soft_blocks
        flame_positions = {flame.position for flame in next_state.flames}
        assert (1, 1) in flame_positions
        assert (2, 1) in flame_positions
        assert (3, 1) not in flame_positions
        assert next_state.cleared_blocks == 1

    def test_bomb_button_is_edge_triggered(self) -> None:
        state = create_initial_bomberman_state(soft_block_density=0.0)
        state = replace(state, soft_blocks=frozenset({(14, 14)}))

        placed = advance_bomberman_state(
            state,
            _frame(16.0),
            BombermanInput(bomb_held=True),
        )
        held = advance_bomberman_state(
            placed,
            _frame(16.0),
            BombermanInput(bomb_held=True),
        )

        assert len(placed.bombs) == 1
        assert len(held.bombs) == 1
        assert held.bombs[0].remaining_ms == BOMB_FUSE_MS - 16.0

    def test_gamepad_dpad_maps_to_grid_direction(self) -> None:
        command = input_from_snapshots(
            KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0),
            GamepadSnapshot(
                connected=True,
                identifier="8bitdo",
                dpad=GamepadDpadValue(y=1),
            ),
        )

        assert command.movement == (0, -1)


class TestBombermanRenderer:
    def test_renderer_paints_16_by_16_board(self, device) -> None:
        surface = pygame.Surface((64, 64), pygame.SRCALPHA)
        window = DisplayContext(
            device=device,
            screen=surface,
            clock=pygame.time.Clock(),
            can_configure_display=False,
        )
        manager = PeripheralManager()
        renderer = BombermanRenderer()
        orientation = Rectangle.with_layout(1, 1)

        renderer.initialize(window, manager, orientation)
        renderer.set_state(create_initial_bomberman_state(soft_block_density=0.0))
        renderer.real_process(window, orientation)

        assert surface.get_at((0, 0))[:3] != (0, 0, 0)
        assert surface.get_at((4, 4))[:3] != surface.get_at((0, 0))[:3]

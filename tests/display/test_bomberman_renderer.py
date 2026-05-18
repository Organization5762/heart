import random
from dataclasses import replace

import pygame

from heart.device import Rectangle
from heart.peripheral.core.input import (FrameTick, GamepadDpadValue,
                                         GamepadSnapshot, KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.streams import EventStream
from heart.renderers.bomberman import BombermanRenderer
from heart.renderers.bomberman.provider import BombermanStateProvider
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

        released = advance_bomberman_state(
            moved,
            _frame(16.0),
            BombermanInput(),
        )
        blocked = advance_bomberman_state(
            released,
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

    def test_quick_direction_tap_buffers_until_step_cooldown_ends(self) -> None:
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
        neutral = advance_bomberman_state(
            moved,
            _frame(16.0),
            BombermanInput(),
        )
        buffered = advance_bomberman_state(
            neutral,
            _frame(16.0),
            BombermanInput(movement=(-1, 0)),
        )
        released = advance_bomberman_state(
            buffered,
            _frame(100.0),
            BombermanInput(),
        )

        assert buffered.player.position == (2, 1)
        assert buffered.player.facing == (-1, 0)
        assert released.player.position == (1, 1)

    def test_held_direction_does_not_repeat_without_release(self) -> None:
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
        held = advance_bomberman_state(
            moved,
            _frame(200.0),
            BombermanInput(movement=(1, 0)),
        )
        released = advance_bomberman_state(
            held,
            _frame(16.0),
            BombermanInput(),
        )
        pressed_again = advance_bomberman_state(
            released,
            _frame(16.0),
            BombermanInput(movement=(1, 0)),
        )

        assert moved.player.position == (2, 1)
        assert held.player.position == (2, 1)
        assert pressed_again.player.position == (3, 1)

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
    def test_provider_applies_latest_gamepad_input_on_frame_tick(
        self,
        monkeypatch,
        stub_clock_factory,
    ) -> None:
        manager = PeripheralManager()
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(
            manager.keyboard_controller,
            "snapshot_stream",
            lambda: keyboard_snapshots.observable(),
        )
        monkeypatch.setattr(
            manager.gamepad_controller,
            "snapshot_stream",
            lambda: gamepad_snapshots.observable(),
        )
        provider = BombermanStateProvider(
            rng=random.Random(1),
            soft_block_density=0.0,
        )
        states = []

        provider.observable(manager).subscribe(states.append)
        gamepad_snapshots.emit(
            GamepadSnapshot(
                connected=True,
                identifier="8bitdo",
                dpad=GamepadDpadValue(x=1),
            )
        )
        manager.frame_tick_controller.advance(stub_clock_factory(16))

        assert states[-1].player.position == (2, 1)

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

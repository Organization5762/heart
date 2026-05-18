from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal

from heart.peripheral.core.input import (FrameTick, GamepadAxis, GamepadButton,
                                         GamepadSnapshot, KeyboardSnapshot)

Coord = tuple[int, int]
Direction = tuple[int, int]
GamePhase = Literal["playing", "cleared", "dead"]

GRID_SIZE = 16
BOMB_FUSE_MS = 1800.0
BOMB_RANGE = 3
FLAME_TTL_MS = 300.0
PLAYER_STEP_MS = 95.0
SOFT_BLOCK_DENSITY = 0.42
SPAWN_CLEAR_CELLS: frozenset[Coord] = frozenset(
    {
        (1, 1),
        (2, 1),
        (1, 2),
        (3, 1),
        (1, 3),
    }
)


@dataclass(frozen=True, slots=True)
class BombermanBomb:
    position: Coord
    remaining_ms: float = BOMB_FUSE_MS
    blast_range: int = BOMB_RANGE


@dataclass(frozen=True, slots=True)
class BombermanFlame:
    position: Coord
    remaining_ms: float = FLAME_TTL_MS


@dataclass(frozen=True, slots=True)
class BombermanPlayer:
    position: Coord = (1, 1)
    facing: Direction = (1, 0)


@dataclass(frozen=True, slots=True)
class BombermanInput:
    movement: Direction | None = None
    bomb_held: bool = False
    reset: bool = False


@dataclass(frozen=True, slots=True)
class BombermanState:
    player: BombermanPlayer
    walls: frozenset[Coord]
    soft_blocks: frozenset[Coord]
    bombs: tuple[BombermanBomb, ...] = ()
    flames: tuple[BombermanFlame, ...] = ()
    phase: GamePhase = "playing"
    bomb_button_held: bool = False
    move_cooldown_ms: float = 0.0
    queued_movement: Direction | None = None
    held_movement: Direction | None = None
    cleared_blocks: int = 0


def create_initial_bomberman_state(
    *,
    rng: random.Random | None = None,
    soft_block_density: float = SOFT_BLOCK_DENSITY,
) -> BombermanState:
    rng = rng or random.Random(0)
    walls = _create_walls()
    soft_blocks = _create_soft_blocks(
        rng=rng,
        walls=walls,
        density=soft_block_density,
    )
    return BombermanState(
        player=BombermanPlayer(),
        walls=walls,
        soft_blocks=soft_blocks,
    )


def input_from_snapshots(
    keyboard: KeyboardSnapshot,
    gamepad: GamepadSnapshot,
) -> BombermanInput:
    movement = _movement_from_gamepad(gamepad) or _movement_from_keyboard(keyboard)
    bomb_held = (
        _key_held(keyboard, "space")
        or _key_held(keyboard, "return")
        or _key_held(keyboard, "x")
        or gamepad.button_held(GamepadButton.SOUTH)
        or gamepad.button_held(GamepadButton.EAST)
        or gamepad.button_tapped(GamepadButton.SOUTH)
        or gamepad.button_tapped(GamepadButton.EAST)
    )
    return BombermanInput(
        movement=movement,
        bomb_held=bomb_held,
        reset=_key_held(keyboard, "r") or gamepad.button_tapped(GamepadButton.NORTH),
    )


def advance_bomberman_state(
    state: BombermanState,
    frame: FrameTick,
    command: BombermanInput,
    *,
    rng: random.Random | None = None,
) -> BombermanState:
    if command.reset:
        return create_initial_bomberman_state(rng=rng)

    if state.phase != "playing":
        return BombermanState(
            player=state.player,
            walls=state.walls,
            soft_blocks=state.soft_blocks,
            bombs=state.bombs,
            flames=_tick_flames(state.flames, frame.delta_ms),
            phase=state.phase,
            bomb_button_held=command.bomb_held,
            move_cooldown_ms=max(0.0, state.move_cooldown_ms - frame.delta_ms),
            queued_movement=state.queued_movement,
            held_movement=command.movement,
            cleared_blocks=state.cleared_blocks,
        )

    bombs, exploded_bombs = _tick_bombs(state.bombs, frame.delta_ms)
    flames = _tick_flames(state.flames, frame.delta_ms)
    soft_blocks = state.soft_blocks
    cleared_blocks = state.cleared_blocks

    if exploded_bombs:
        flame_cells = _explosion_cells(
            exploded_bombs=exploded_bombs,
            walls=state.walls,
            soft_blocks=soft_blocks,
        )
        cleared_now = soft_blocks.intersection(flame_cells)
        soft_blocks = frozenset(soft_blocks.difference(cleared_now))
        cleared_blocks += len(cleared_now)
        flames = tuple(BombermanFlame(cell) for cell in sorted(flame_cells))

    player = state.player
    phase: GamePhase = "playing"
    if any(flame.position == player.position for flame in flames):
        phase = "dead"

    if (
        phase == "playing"
        and command.bomb_held
        and not state.bomb_button_held
        and not bombs
        and player.position not in {bomb.position for bomb in bombs}
    ):
        bombs = (*bombs, BombermanBomb(position=player.position))

    move_cooldown_ms = max(0.0, state.move_cooldown_ms - frame.delta_ms)
    movement_pressed = state.held_movement is None and command.movement is not None
    queued_movement = state.queued_movement or (
        command.movement if movement_pressed else None
    )
    if phase == "playing" and queued_movement is not None:
        if move_cooldown_ms > 0:
            player = BombermanPlayer(
                position=player.position,
                facing=queued_movement,
            )
        else:
            player, move_cooldown_ms = _advance_player(
                player=player,
                movement=queued_movement,
                move_cooldown_ms=move_cooldown_ms,
                walls=state.walls,
                soft_blocks=soft_blocks,
                bombs=bombs,
            )
            queued_movement = None

    if phase == "playing" and not soft_blocks:
        phase = "cleared"

    return BombermanState(
        player=player,
        walls=state.walls,
        soft_blocks=soft_blocks,
        bombs=bombs,
        flames=flames,
        phase=phase,
        bomb_button_held=command.bomb_held,
        move_cooldown_ms=move_cooldown_ms,
        queued_movement=queued_movement,
        held_movement=command.movement,
        cleared_blocks=cleared_blocks,
    )


def _create_walls() -> frozenset[Coord]:
    walls: set[Coord] = set()
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if x == 0 or y == 0 or x == GRID_SIZE - 1 or y == GRID_SIZE - 1:
                walls.add((x, y))
            elif x % 2 == 0 and y % 2 == 0:
                walls.add((x, y))
    return frozenset(walls)


def _create_soft_blocks(
    *,
    rng: random.Random,
    walls: frozenset[Coord],
    density: float,
) -> frozenset[Coord]:
    soft_blocks: set[Coord] = set()
    for y in range(1, GRID_SIZE - 1):
        for x in range(1, GRID_SIZE - 1):
            cell = (x, y)
            if cell in walls or cell in SPAWN_CLEAR_CELLS:
                continue
            if rng.random() < density:
                soft_blocks.add(cell)
    return frozenset(soft_blocks)


def _tick_bombs(
    bombs: tuple[BombermanBomb, ...],
    delta_ms: float,
) -> tuple[tuple[BombermanBomb, ...], tuple[BombermanBomb, ...]]:
    active: list[BombermanBomb] = []
    exploded: list[BombermanBomb] = []
    for bomb in bombs:
        updated = BombermanBomb(
            position=bomb.position,
            remaining_ms=bomb.remaining_ms - delta_ms,
            blast_range=bomb.blast_range,
        )
        if updated.remaining_ms <= 0:
            exploded.append(updated)
        else:
            active.append(updated)
    return tuple(active), tuple(exploded)


def _tick_flames(
    flames: tuple[BombermanFlame, ...],
    delta_ms: float,
) -> tuple[BombermanFlame, ...]:
    return tuple(
        BombermanFlame(
            position=flame.position,
            remaining_ms=flame.remaining_ms - delta_ms,
        )
        for flame in flames
        if flame.remaining_ms > delta_ms
    )


def _explosion_cells(
    *,
    exploded_bombs: tuple[BombermanBomb, ...],
    walls: frozenset[Coord],
    soft_blocks: frozenset[Coord],
) -> frozenset[Coord]:
    cells: set[Coord] = set()
    for bomb in exploded_bombs:
        cells.add(bomb.position)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for step in range(1, bomb.blast_range + 1):
                cell = (bomb.position[0] + dx * step, bomb.position[1] + dy * step)
                if cell in walls:
                    break
                cells.add(cell)
                if cell in soft_blocks:
                    break
    return frozenset(cells)


def _advance_player(
    *,
    player: BombermanPlayer,
    movement: Direction,
    move_cooldown_ms: float,
    walls: frozenset[Coord],
    soft_blocks: frozenset[Coord],
    bombs: tuple[BombermanBomb, ...],
) -> tuple[BombermanPlayer, float]:
    if move_cooldown_ms > 0:
        return BombermanPlayer(position=player.position, facing=movement), move_cooldown_ms

    target = (player.position[0] + movement[0], player.position[1] + movement[1])
    blocked = set(walls).union(soft_blocks).union(bomb.position for bomb in bombs)
    if target in blocked:
        return BombermanPlayer(position=player.position, facing=movement), 0.0

    return BombermanPlayer(position=target, facing=movement), PLAYER_STEP_MS


def _movement_from_gamepad(gamepad: GamepadSnapshot) -> Direction | None:
    if gamepad.dpad.x != 0:
        return (1 if gamepad.dpad.x > 0 else -1, 0)
    if gamepad.dpad.y != 0:
        return (0, -1 if gamepad.dpad.y > 0 else 1)

    x_axis = gamepad.axis_value(GamepadAxis.LEFT_X, dead_zone=0.35)
    y_axis = gamepad.axis_value(GamepadAxis.LEFT_Y, dead_zone=0.35)
    if abs(x_axis) >= abs(y_axis) and x_axis != 0:
        return (1 if x_axis > 0 else -1, 0)
    if y_axis != 0:
        return (0, 1 if y_axis > 0 else -1)
    return None


def _movement_from_keyboard(keyboard: KeyboardSnapshot) -> Direction | None:
    if _key_held(keyboard, "left") or _key_held(keyboard, "a"):
        return (-1, 0)
    if _key_held(keyboard, "right") or _key_held(keyboard, "d"):
        return (1, 0)
    if _key_held(keyboard, "up") or _key_held(keyboard, "w"):
        return (0, -1)
    if _key_held(keyboard, "down") or _key_held(keyboard, "s"):
        return (0, 1)
    return None


def _key_held(keyboard: KeyboardSnapshot, key_name: str) -> bool:
    import pygame

    return pygame.key.key_code(key_name) in keyboard.pressed_keys

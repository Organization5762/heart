from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from typing import Deque

BOARD_WIDTH = 10
BOARD_HEIGHT = 20
CELL_SIZE_PX = 3
PLAYER_COUNT = 4
QUEUE_PREVIEW_LENGTH = 6
LINES_PER_LEVEL = 10
MAX_GRAVITY_LEVEL = 15
FALL_INTERVAL_MS = 1000.0
SOFT_DROP_INTERVAL_MS = 120
SOFT_DROP_GRAVITY_MULTIPLIER = 20
SOFT_DROP_MIN_INTERVAL_MS = 16.0
LOCK_DELAY_MS = 450
MOVE_REPEAT_DELAY_MS = 80
MOVE_REPEAT_INTERVAL_MS = 35


class TetrisPieceKind(StrEnum):
    I_PIECE = "I"
    O_PIECE = "O"
    T_PIECE = "T"
    S_PIECE = "S"
    Z_PIECE = "Z"
    J_PIECE = "J"
    L_PIECE = "L"


class TetrisColor(IntEnum):
    CYAN = 1
    YELLOW = 2
    PURPLE = 3
    GREEN = 4
    RED = 5
    BLUE = 6
    ORANGE = 7
    GARBAGE = 8


PIECE_COLORS: dict[TetrisPieceKind, TetrisColor] = {
    TetrisPieceKind.I_PIECE: TetrisColor.CYAN,
    TetrisPieceKind.O_PIECE: TetrisColor.YELLOW,
    TetrisPieceKind.T_PIECE: TetrisColor.PURPLE,
    TetrisPieceKind.S_PIECE: TetrisColor.GREEN,
    TetrisPieceKind.Z_PIECE: TetrisColor.RED,
    TetrisPieceKind.J_PIECE: TetrisColor.BLUE,
    TetrisPieceKind.L_PIECE: TetrisColor.ORANGE,
}

PIECE_ROTATIONS: dict[TetrisPieceKind, tuple[tuple[tuple[int, int], ...], ...]] = {
    TetrisPieceKind.I_PIECE: (
        ((0, 1), (1, 1), (2, 1), (3, 1)),
        ((2, 0), (2, 1), (2, 2), (2, 3)),
        ((0, 2), (1, 2), (2, 2), (3, 2)),
        ((1, 0), (1, 1), (1, 2), (1, 3)),
    ),
    TetrisPieceKind.O_PIECE: (
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
    ),
    TetrisPieceKind.T_PIECE: (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    TetrisPieceKind.S_PIECE: (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((1, 0), (1, 1), (2, 1), (2, 2)),
        ((1, 1), (2, 1), (0, 2), (1, 2)),
        ((0, 0), (0, 1), (1, 1), (1, 2)),
    ),
    TetrisPieceKind.Z_PIECE: (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((2, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (1, 2), (2, 2)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
    TetrisPieceKind.J_PIECE: (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (2, 2)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    TetrisPieceKind.L_PIECE: (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (1, 2), (2, 2)),
        ((0, 1), (1, 1), (2, 1), (0, 2)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
}


@dataclass(frozen=True, slots=True)
class TetrisPiece:
    kind: TetrisPieceKind
    rotation: int = 0
    x: int = 3
    y: int = 0

    @property
    def color(self) -> TetrisColor:
        return PIECE_COLORS[self.kind]

    def cells(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (self.x + dx, self.y + dy)
            for dx, dy in PIECE_ROTATIONS[self.kind][self.rotation % 4]
        )

    def moved(self, dx: int, dy: int) -> "TetrisPiece":
        return TetrisPiece(
            kind=self.kind,
            rotation=self.rotation,
            x=self.x + dx,
            y=self.y + dy,
        )

    def rotated(self, steps: int = 1) -> "TetrisPiece":
        return TetrisPiece(
            kind=self.kind,
            rotation=(self.rotation + steps) % 4,
            x=self.x,
            y=self.y,
        )


@dataclass(frozen=True, slots=True)
class TetrisControls:
    move_x: int = 0
    soft_drop: bool = False
    hard_drop: bool = False
    rotate_cw: bool = False
    rotate_ccw: bool = False
    hold: bool = False
    restart: bool = False


@dataclass(slots=True)
class TetrisInputMemory:
    previous_move_x: int = 0
    held_move_x: int = 0
    move_repeat_elapsed_ms: float = 0.0
    move_repeat_primed: bool = False
    previous_dpad_y: int = 0
    soft_drop_elapsed_ms: float = 0.0


@dataclass(slots=True)
class TetrisPlayerState:
    board: list[list[TetrisColor | None]]
    active: TetrisPiece | None
    next_queue: Deque[TetrisPieceKind]
    hold_piece: TetrisPieceKind | None = None
    hold_used: bool = False
    fall_elapsed_ms: float = 0.0
    lock_elapsed_ms: float = 0.0
    pending_garbage: int = 0
    score: int = 0
    lines_cleared: int = 0
    game_over: bool = False
    input_memory: TetrisInputMemory = field(default_factory=TetrisInputMemory)

    @classmethod
    def create(cls, rng: random.Random) -> "TetrisPlayerState":
        player = cls(
            board=empty_board(),
            active=None,
            next_queue=deque(),
        )
        fill_queue(player.next_queue, rng)
        spawn_next_piece(player, rng)
        return player


@dataclass(slots=True)
class TetrisGameState:
    players: list[TetrisPlayerState]
    match_finished: bool = False
    winner_index: int | None = None

    @classmethod
    def create(
        cls, rng: random.Random, player_count: int = PLAYER_COUNT
    ) -> "TetrisGameState":
        return cls(players=[TetrisPlayerState.create(rng) for _ in range(player_count)])


def empty_board() -> list[list[TetrisColor | None]]:
    return [[None for _ in range(BOARD_WIDTH)] for _ in range(BOARD_HEIGHT)]


def fill_queue(queue: Deque[TetrisPieceKind], rng: random.Random) -> None:
    while len(queue) < QUEUE_PREVIEW_LENGTH + 1:
        bag = list(TetrisPieceKind)
        rng.shuffle(bag)
        queue.extend(bag)


def spawn_next_piece(player: TetrisPlayerState, rng: random.Random) -> None:
    fill_queue(player.next_queue, rng)
    kind = player.next_queue.popleft()
    player.active = TetrisPiece(kind=kind)
    player.hold_used = False
    player.lock_elapsed_ms = 0.0
    player.fall_elapsed_ms = 0.0
    fill_queue(player.next_queue, rng)
    if collides(player.board, player.active):
        player.game_over = True


def collides(board: list[list[TetrisColor | None]], piece: TetrisPiece) -> bool:
    for x, y in piece.cells():
        if x < 0 or x >= BOARD_WIDTH or y >= BOARD_HEIGHT:
            return True
        if y >= 0 and board[y][x] is not None:
            return True
    return False


def try_move(player: TetrisPlayerState, dx: int, dy: int) -> bool:
    if player.active is None:
        return False
    candidate = player.active.moved(dx, dy)
    if collides(player.board, candidate):
        return False
    player.active = candidate
    if dy == 0:
        player.lock_elapsed_ms = 0.0
    return True


def try_rotate(player: TetrisPlayerState, steps: int) -> bool:
    if player.active is None:
        return False
    candidate = player.active.rotated(steps)
    for kick_x in (0, -1, 1, -2, 2):
        kicked = TetrisPiece(
            kind=candidate.kind,
            rotation=candidate.rotation,
            x=candidate.x + kick_x,
            y=candidate.y,
        )
        if not collides(player.board, kicked):
            player.active = kicked
            player.lock_elapsed_ms = 0.0
            return True
    return False


def hold_piece(player: TetrisPlayerState, rng: random.Random) -> None:
    if player.active is None or player.hold_used:
        return
    active_kind = player.active.kind
    if player.hold_piece is None:
        player.hold_piece = active_kind
        spawn_next_piece(player, rng)
    else:
        player.active = TetrisPiece(kind=player.hold_piece)
        player.hold_piece = active_kind
        if collides(player.board, player.active):
            player.game_over = True
    player.hold_used = True


def hard_drop(player: TetrisPlayerState, rng: random.Random) -> int:
    if player.active is None:
        return 0
    distance = 0
    while try_move(player, 0, 1):
        distance += 1
    player.score += distance * 2
    return lock_piece(player, rng)


def lock_piece(player: TetrisPlayerState, rng: random.Random) -> int:
    if player.active is None:
        return 0
    for x, y in player.active.cells():
        if y < 0:
            player.game_over = True
            player.active = None
            return 0
        player.board[y][x] = player.active.color
    player.active = None
    cleared = clear_lines(player)
    if player.pending_garbage > 0:
        apply_garbage(player, player.pending_garbage, rng)
        player.pending_garbage = 0
    spawn_next_piece(player, rng)
    return cleared


def clear_lines(player: TetrisPlayerState) -> int:
    remaining = [row for row in player.board if any(cell is None for cell in row)]
    cleared = BOARD_HEIGHT - len(remaining)
    if cleared == 0:
        return 0
    player.board[:] = [
        [None for _ in range(BOARD_WIDTH)] for _ in range(cleared)
    ] + remaining
    player.lines_cleared += cleared
    player.score += (100, 300, 500, 800)[min(cleared, 4) - 1]
    return cleared


def player_level(player: TetrisPlayerState) -> int:
    return (player.lines_cleared // LINES_PER_LEVEL) + 1


def guideline_fall_interval_ms(level: int) -> float:
    gravity_level = max(1, min(level, MAX_GRAVITY_LEVEL))
    seconds_per_row = (0.8 - ((gravity_level - 1) * 0.007)) ** (gravity_level - 1)
    return seconds_per_row * FALL_INTERVAL_MS


def soft_drop_interval_ms(level: int) -> float:
    return min(
        SOFT_DROP_INTERVAL_MS,
        max(
            SOFT_DROP_MIN_INTERVAL_MS,
            guideline_fall_interval_ms(level) / SOFT_DROP_GRAVITY_MULTIPLIER,
        ),
    )


def apply_garbage(
    player: TetrisPlayerState,
    line_count: int,
    rng: random.Random,
) -> None:
    for _ in range(line_count):
        hole = rng.randrange(BOARD_WIDTH)
        player.board.pop(0)
        player.board.append(
            [None if x == hole else TetrisColor.GARBAGE for x in range(BOARD_WIDTH)]
        )
    if player.active is not None and collides(player.board, player.active):
        while player.active is not None and collides(player.board, player.active):
            player.active = player.active.moved(0, -1)
            if any(y < 0 for _, y in player.active.cells()):
                player.game_over = True
                return


def queue_garbage_for_opponents(
    state: TetrisGameState,
    sender_index: int,
    line_count: int,
) -> None:
    if line_count <= 0:
        return
    for index, player in enumerate(state.players):
        if index == sender_index or player.game_over:
            continue
        player.pending_garbage += line_count


def update_match_end_state(state: TetrisGameState) -> None:
    if state.match_finished:
        return
    alive_indices = [
        index for index, player in enumerate(state.players) if not player.game_over
    ]
    if len(alive_indices) > 1:
        return
    state.match_finished = True
    state.winner_index = alive_indices[0] if alive_indices else None


def restart_match(state: TetrisGameState, rng: random.Random) -> None:
    replacement = TetrisGameState.create(rng, player_count=len(state.players))
    state.players = replacement.players
    state.match_finished = False
    state.winner_index = None


def restart_player(player: TetrisPlayerState, rng: random.Random) -> None:
    replacement = TetrisPlayerState.create(rng)
    player.board = replacement.board
    player.active = replacement.active
    player.next_queue = replacement.next_queue
    player.hold_piece = replacement.hold_piece
    player.hold_used = replacement.hold_used
    player.fall_elapsed_ms = replacement.fall_elapsed_ms
    player.lock_elapsed_ms = replacement.lock_elapsed_ms
    player.pending_garbage = replacement.pending_garbage
    player.score = replacement.score
    player.lines_cleared = replacement.lines_cleared
    player.game_over = replacement.game_over
    player.input_memory = replacement.input_memory


def advance_player(
    player: TetrisPlayerState,
    controls: TetrisControls,
    elapsed_ms: float,
    rng: random.Random,
) -> int:
    if controls.restart:
        restart_player(player, rng)
        return 0
    if player.game_over:
        return 0

    if controls.hold:
        hold_piece(player, rng)
    if controls.rotate_cw:
        try_rotate(player, 1)
    if controls.rotate_ccw:
        try_rotate(player, -1)

    move_x = controls.move_x
    if move_x != 0:
        try_move(player, move_x, 0)

    if controls.hard_drop:
        return hard_drop(player, rng)

    level = player_level(player)
    if controls.soft_drop:
        soft_drop_interval = soft_drop_interval_ms(level)
        player.fall_elapsed_ms = 0.0
        player.input_memory.soft_drop_elapsed_ms += elapsed_ms
        if player.input_memory.soft_drop_elapsed_ms < soft_drop_interval:
            return 0
        player.input_memory.soft_drop_elapsed_ms = 0.0
        if try_move(player, 0, 1):
            player.score += 1
            player.lock_elapsed_ms = 0.0
            return 0
        player.lock_elapsed_ms += soft_drop_interval
        if player.lock_elapsed_ms >= LOCK_DELAY_MS:
            return lock_piece(player, rng)
        return 0

    player.input_memory.soft_drop_elapsed_ms = 0.0
    fall_interval = guideline_fall_interval_ms(level)
    player.fall_elapsed_ms += elapsed_ms
    cleared = 0
    while player.fall_elapsed_ms >= fall_interval and not player.game_over:
        player.fall_elapsed_ms -= fall_interval
        if try_move(player, 0, 1):
            if controls.soft_drop:
                player.score += 1
            player.lock_elapsed_ms = 0.0
            continue
        player.lock_elapsed_ms += fall_interval
        if player.lock_elapsed_ms >= LOCK_DELAY_MS:
            cleared += lock_piece(player, rng)
            break
    return cleared

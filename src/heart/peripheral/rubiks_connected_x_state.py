"""Cube-state helpers for Rubik's Connected X move streams."""

from __future__ import annotations

from typing import Final

from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_FACE_ORDER,
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
)

AXIS_INDEX: Final[dict[str, int]] = {"x": 0, "y": 1, "z": 2}
FACE_TO_VECTOR: Final[dict[str, tuple[int, int, int]]] = {
    "U": (0, 1, 0),
    "R": (1, 0, 0),
    "F": (0, 0, 1),
    "D": (0, -1, 0),
    "L": (-1, 0, 0),
    "B": (0, 0, -1),
}
MOVE_ROTATIONS: Final[dict[str, tuple[str, int, int]]] = {
    "U": ("y", 1, 1),
    "D": ("y", -1, -1),
    "F": ("z", 1, -1),
    "B": ("z", -1, 1),
    "R": ("x", 1, -1),
    "L": ("x", -1, 1),
}


def apply_rubiks_connected_x_moves(
    facelets: str,
    moves: tuple[str, ...],
) -> str:
    """Apply a sequence of standard move notations to a facelet string."""

    updated = facelets
    for move in moves:
        updated = apply_rubiks_connected_x_move(updated, move)
    return updated


def apply_rubiks_connected_x_move(facelets: str, move: str) -> str:
    """Apply one standard move notation to a facelet string."""

    if len(facelets) != len(RUBIKS_CONNECTED_X_SOLVED_FACELETS):
        raise ValueError("Cube facelets must contain 54 stickers.")
    if not move:
        raise ValueError("Move notation cannot be empty.")
    face = move[0]
    if face not in MOVE_ROTATIONS:
        raise ValueError(f"Unsupported move face: {face}")
    turns = 1
    if move.endswith("2"):
        turns = 2
    elif move.endswith("'"):
        turns = 3
    axis, layer_value, clockwise_turn = MOVE_ROTATIONS[face]
    quarter_turns = (clockwise_turn * turns) % 4
    if quarter_turns == 0:
        return facelets

    updated = ["?"] * len(facelets)
    for source_index, sticker in enumerate(facelets):
        position, normal = _index_to_geometry(source_index)
        if position[AXIS_INDEX[axis]] == layer_value:
            position = _rotate_vector(position, axis, quarter_turns)
            normal = _rotate_vector(normal, axis, quarter_turns)
        destination_index = _geometry_to_index(position, normal)
        updated[destination_index] = sticker
    return "".join(updated)


def _rotate_vector(
    vector: tuple[int, int, int],
    axis: str,
    quarter_turns: int,
) -> tuple[int, int, int]:
    x_value, y_value, z_value = vector
    for _ in range(quarter_turns % 4):
        if axis == "x":
            y_value, z_value = -z_value, y_value
        elif axis == "y":
            x_value, z_value = z_value, -x_value
        elif axis == "z":
            x_value, y_value = -y_value, x_value
        else:
            raise ValueError(f"Unsupported axis: {axis}")
    return (x_value, y_value, z_value)


def _index_to_geometry(index: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    face = RUBIKS_CONNECTED_X_FACE_ORDER[index // 9]
    face_index = index % 9
    row_index, column_index = divmod(face_index, 3)
    if face == "U":
        return ((column_index - 1, 1, row_index - 1), FACE_TO_VECTOR[face])
    if face == "D":
        return ((column_index - 1, -1, 1 - row_index), FACE_TO_VECTOR[face])
    if face == "F":
        return ((column_index - 1, 1 - row_index, 1), FACE_TO_VECTOR[face])
    if face == "B":
        return ((1 - column_index, 1 - row_index, -1), FACE_TO_VECTOR[face])
    if face == "R":
        return ((1, 1 - row_index, 1 - column_index), FACE_TO_VECTOR[face])
    if face == "L":
        return ((-1, 1 - row_index, column_index - 1), FACE_TO_VECTOR[face])
    raise ValueError(f"Unsupported face: {face}")


def _geometry_to_index(
    position: tuple[int, int, int],
    normal: tuple[int, int, int],
) -> int:
    x_value, y_value, z_value = position
    if normal == FACE_TO_VECTOR["U"]:
        return _face_index("U", z_value + 1, x_value + 1)
    if normal == FACE_TO_VECTOR["D"]:
        return _face_index("D", 1 - z_value, x_value + 1)
    if normal == FACE_TO_VECTOR["F"]:
        return _face_index("F", 1 - y_value, x_value + 1)
    if normal == FACE_TO_VECTOR["B"]:
        return _face_index("B", 1 - y_value, 1 - x_value)
    if normal == FACE_TO_VECTOR["R"]:
        return _face_index("R", 1 - y_value, 1 - z_value)
    if normal == FACE_TO_VECTOR["L"]:
        return _face_index("L", 1 - y_value, z_value + 1)
    raise ValueError(f"Unsupported normal vector: {normal}")


def _face_index(face: str, row_index: int, column_index: int) -> int:
    return (
        (RUBIKS_CONNECTED_X_FACE_ORDER.index(face) * 9) + (row_index * 3) + column_index
    )

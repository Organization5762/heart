"""Validate local cube-state updates for move-only Rubik's Connected X sessions."""

from __future__ import annotations

from heart.peripheral.rubiks_connected_x import RUBIKS_CONNECTED_X_SOLVED_FACELETS
from heart.peripheral.rubiks_connected_x_state import (
    apply_rubiks_connected_x_move,
    apply_rubiks_connected_x_moves,
)


class TestRubiksConnectedXStateHelpers:
    """Cover local move application so the visualizer stays usable even before full-state sync lands."""

    def test_move_and_inverse_return_to_solved(self) -> None:
        """Verify inverse turns cancel out so move-only visualization does not accumulate drift during normal play."""

        updated = apply_rubiks_connected_x_moves(
            RUBIKS_CONNECTED_X_SOLVED_FACELETS,
            ("F", "F'"),
        )

        assert updated == RUBIKS_CONNECTED_X_SOLVED_FACELETS

    def test_four_quarter_turns_return_to_solved(self) -> None:
        """Verify repeated quarter turns cycle correctly so the local simulator preserves basic cube-group invariants."""

        updated = RUBIKS_CONNECTED_X_SOLVED_FACELETS
        for _ in range(4):
            updated = apply_rubiks_connected_x_move(updated, "U")

        assert updated == RUBIKS_CONNECTED_X_SOLVED_FACELETS

    def test_single_move_changes_state(self) -> None:
        """Verify a lone turn mutates the cube so the visualizer can show live change as soon as move packets arrive."""

        updated = apply_rubiks_connected_x_move(
            RUBIKS_CONNECTED_X_SOLVED_FACELETS,
            "R",
        )

        assert updated != RUBIKS_CONNECTED_X_SOLVED_FACELETS

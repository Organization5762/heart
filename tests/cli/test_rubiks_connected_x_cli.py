"""Validate Rubik's Connected X CLI helpers for calibration workflows."""

from __future__ import annotations

from heart.cli.commands.rubiks_connected_x import (
    _normalize_calibration_moves,
    _render_calibration_summary,
    _render_state_summary,
    DEFAULT_BASELINE_OUTPUT_PATH,
)
from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE,
    RubiksConnectedXNotification,
    parse_rubiks_connected_x_packet,
)


class TestRubiksConnectedXCliHelpers:
    """Cover CLI calibration helpers so guided cube capture stays consistent and readable across sessions."""

    def test_normalize_calibration_moves_uses_defaults_for_empty_values(self) -> None:
        """Verify empty move inputs fall back to the default move plan so operators can start calibration without extra flags."""

        assert _normalize_calibration_moves(None) == ("U", "U'", "R", "R'", "F", "F'")
        assert _normalize_calibration_moves(["", "  "]) == (
            "U",
            "U'",
            "R",
            "R'",
            "F",
            "F'",
        )

    def test_render_calibration_summary_includes_packet_counts(self) -> None:
        """Verify move summaries surface grouped packet signatures so calibration output stays compact enough to compare labeled turns by eye."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 03 09 3d 0d 0a")
        )
        notifications = [
            RubiksConnectedXNotification(
                characteristic_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
                payload_hex="2a 06 01 03 09 3d 0d 0a",
                payload_utf8="*\x06\x01\x03\t=",
                byte_count=8,
                sequence=1,
                parsed_packet=packet,
            )
        ]

        summary = _render_calibration_summary("U", notifications)

        assert "U: total=1" in summary
        assert "face=3" in summary
        assert "turn=9" in summary

    def test_render_state_summary_groups_each_face(self) -> None:
        """Verify state summaries print one 3x3 section per URFDLB face so solved-orientation calibration can compare parsed faces to the real cube unambiguously."""

        summary = _render_state_summary(
            "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
        )

        assert "U\nUUU\nUUU\nUUU" in summary
        assert "F\nFFF\nFFF\nFFF" in summary
        assert "B\nBBB\nBBB\nBBB" in summary

    def test_baseline_output_path_defaults_to_repo_friendly_text_file(self) -> None:
        """Verify baseline capture writes to a stable text filename by default so operators can re-use the saved local solved mask across launches without extra path bookkeeping."""

        assert DEFAULT_BASELINE_OUTPUT_PATH.name == "rubiks_connected_x_baseline.txt"

    def test_capture_gesture_is_back_and_forth_top_face_wiggle(self) -> None:
        """Verify the baked-in recovery gesture stays a simple reversible top-face wiggle so operators can trigger baseline capture in the field without changing the cube state."""

        assert RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE == (
            "U",
            "U'",
            "U",
            "U'",
            "U",
            "U'",
            "U",
            "U'",
        )

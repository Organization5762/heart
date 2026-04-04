from __future__ import annotations

from heart.cli.commands.flowtoy import _build_user_pattern, _render_packet_line


class TestFlowToyCommandHelpers:
    """Validate FlowToy command helpers so the totem CLI stays readable while still targeting the correct RF values."""

    def test_build_user_pattern_converts_one_based_values(self) -> None:
        """Verify user-facing page and mode values are converted to zero-based wire values so operators can use the same numbering they see on props."""
        pattern = _build_user_pattern(group_id=2575, page=2, mode=2)

        assert pattern.to_serial_command() == "p2575,1,1,0,0,0,0,0,0,0,0,0,0"

    def test_render_packet_line_reports_user_facing_values(self) -> None:
        """Verify rendered packet summaries convert decoded wire values back to 1-based numbering so live CLI output matches the FlowToy UI."""
        rendered = _render_packet_line(
            "/dev/ttyACM2",
            {"group_id": 2575, "page": 1, "mode": 1},
            -89.0,
        )

        assert rendered == "/dev/ttyACM2 group_id=2575 user_page=2 user_mode=2 rssi=-89.0"

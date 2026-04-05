from __future__ import annotations

import pytest
import typer

from heart.cli.commands.flowtoy import (_build_pattern_from_decoded,
                                        _build_pattern_from_user_values,
                                        _build_user_pattern,
                                        _render_packet_line)


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

    def test_build_pattern_from_decoded_preserves_sync_fields_when_brightness_changes(self) -> None:
        """Verify brightness-only updates reuse the observed sync packet state so manual CLI adjustments do not zero out unrelated FlowToy controls."""
        pattern = _build_pattern_from_decoded(
            decoded={
                "group_id": 2575,
                "page": 1,
                "mode": 4,
                "lfo": [9, 8, 7, 6],
                "global": {
                    "hue": 11,
                    "saturation": 22,
                    "brightness": 33,
                    "speed": 44,
                    "density": 55,
                },
                "active_flags": {
                    "lfo": False,
                    "hue": True,
                    "saturation": False,
                    "brightness": False,
                    "speed": True,
                    "density": False,
                },
            },
            group_id=2575,
            brightness=99,
        )

        assert pattern.to_serial_command() == "p2575,1,4,26,11,22,99,44,55,9,8,7,6"

    def test_build_pattern_from_decoded_rejects_zero_based_page_override(self) -> None:
        """Verify user-facing page and mode overrides stay 1-based so CLI operators cannot accidentally send underflowed sync-packet targets."""
        with pytest.raises(typer.BadParameter):
            _build_pattern_from_decoded(
                decoded={"page": 1, "mode": 1},
                group_id=2575,
                page=0,
            )

    def test_build_pattern_from_decoded_applies_all_global_overrides(self) -> None:
        """Verify direct sync-field overrides replace the observed packet values so operators can tune FlowToy state without editing code."""
        pattern = _build_pattern_from_decoded(
            decoded={
                "group_id": 2575,
                "page": 1,
                "mode": 4,
                "lfo": [9, 8, 7, 6],
                "global": {
                    "hue": 11,
                    "saturation": 22,
                    "brightness": 33,
                    "speed": 44,
                    "density": 55,
                },
                "active_flags": {
                    "lfo": False,
                    "hue": False,
                    "saturation": False,
                    "brightness": False,
                    "speed": False,
                    "density": False,
                },
            },
            group_id=2575,
            hue_offset=101,
            saturation=102,
            brightness=103,
            speed=104,
            density=105,
        )

        assert pattern.to_serial_command() == "p2575,1,4,62,101,102,103,104,105,9,8,7,6"

    def test_build_pattern_from_user_values_supports_all_global_overrides(self) -> None:
        """Verify explicit CLI-only overrides can build a full sync packet so quiet props still accept direct FlowToy tuning commands."""
        pattern = _build_pattern_from_user_values(
            group_id=2575,
            page=1,
            mode=6,
            hue_offset=1,
            saturation=2,
            brightness=3,
            speed=4,
            density=5,
        )

        assert pattern.to_serial_command() == "p2575,0,5,62,1,2,3,4,5,0,0,0,0"

    def test_build_pattern_from_decoded_allows_raw_actives_override(self) -> None:
        """Verify raw actives overrides win when supplied so low-level debugging can reproduce exact FlowToy bit patterns."""
        pattern = _build_pattern_from_decoded(
            decoded={"page": 0, "mode": 5, "global": {}, "active_flags": {}},
            group_id=2575,
            actives=17,
            brightness=80,
        )

        assert pattern.to_serial_command() == "p2575,0,5,17,0,0,80,0,0,0,0,0,0"

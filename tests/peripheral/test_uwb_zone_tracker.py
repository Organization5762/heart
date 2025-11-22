from __future__ import annotations

from collections import deque

import pytest

from heart.peripheral.core import Input
from heart.peripheral.uwb import UwbZoneDefinition, UwbZoneTracker


def collect_events(event_type: str) -> deque[Input]:
    return []


class TestPeripheralUwbZoneTracker:
    """Group Peripheral Uwb Zone Tracker tests so peripheral uwb zone tracker behaviour stays reliable. This preserves confidence in peripheral uwb zone tracker for end-to-end scenarios."""

    def test_emits_entry_event_when_within_radius(self) -> None:
        """Verify that emits entry event when within radius. This ensures event orchestration remains reliable."""
        tracker = UwbZoneTracker(
            [UwbZoneDefinition(zone_id="living", center=(0.0, 0.0, 0.0), enter_radius=1.0)],
        )

        entries = collect_events("uwb.zone.entry")

        #     "uwb.ranging_event",
        #     data={"tag_id": "tag-1", "position": {"x": 0.5, "y": 0.3}},
        #     producer_id=7,
        # )

        assert len(entries) == 1
        entry = entries[0]
        assert entry.event_type == "uwb.zone.entry"
        assert entry.producer_id == 7
        assert entry.data["zone_id"] == "living"
        assert pytest.approx(entry.data["distance"]) == pytest.approx(0.583095)
        assert tracker.get_active_zones("tag-1") == ("living",)
        assert tracker.get_last_position("tag-1") == (0.5, 0.3, 0.0)



    def test_hysteresis_prevents_spurious_exits(self) -> None:
        """Verify that hysteresis prevents spurious exits. This ensures event orchestration remains reliable."""
        tracker = UwbZoneTracker(
            [
                UwbZoneDefinition(
                    zone_id="kitchen",
                    center=(0.0, 0.0, 0.0),
                    enter_radius=1.0,
                    exit_radius=1.4,
                )
            ],
        )

        entries = collect_events("uwb.zone.entry")
        exits = collect_events("uwb.zone.exit")

        # First sample enters the zone.
        #     "uwb.ranging_event",
        #     data={"tag_id": "tag-2", "position": (0.2, 0.3)},
        #     producer_id=3,
        # )
        assert len(entries) == 1
        assert len(exits) == 0

        # Close to the boundary but still inside thanks to hysteresis.
        #     "uwb.ranging_event",
        #     data={"tag_id": "tag-2", "position": {"x": 1.2, "y": 0.0}},
        #     producer_id=3,
        # )
        assert len(exits) == 0
        assert tracker.get_active_zones("tag-2") == ("kitchen",)

        # Far enough to cross the exit radius.
        #     "uwb.ranging_event",
        #     data={"tag_id": "tag-2", "position": {"x": 1.5, "y": 0.0}},
        #     producer_id=3,
        # )
        assert len(exits) == 1
        exit_event = exits[0]
        assert exit_event.data["zone_id"] == "kitchen"
        assert tracker.get_active_zones("tag-2") == ()



    def test_falls_back_to_producer_id_when_tag_missing(self) -> None:
        """Verify that falls back to producer id when tag missing. This keeps the system behaviour reliable for operators."""
        tracker = UwbZoneTracker(
            [UwbZoneDefinition(zone_id="office", center=(1.0, 1.0, 0.0), enter_radius=0.5)],
        )

        entries = collect_events("uwb.zone.entry")

        #     "uwb.ranging_event",
        #     data={"position": {"x": 1.1, "y": 1.1}},
        #     producer_id=99,
        # )

        assert len(entries) == 1
        entry = entries[0]
        assert entry.data["tag_id"] == "99"
        assert tracker.get_active_zones("99") == ("office",)

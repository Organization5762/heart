from datetime import datetime
from typing import cast

from heart.peripheral.core import Input, StateStore


class TestPeripheralStateStore:
    """Group Peripheral State Store tests so peripheral state store behaviour stays reliable. This preserves confidence in peripheral state store for end-to-end scenarios."""

    def test_state_store_tracks_latest_events_by_producer(self) -> None:
        """Verify that StateStore tracks the latest event per producer. This keeps peripherals able to query current state instantly."""
        store = StateStore()
        event_a = Input(event_type="switch/press", data={"pressed": True}, producer_id=0)
        event_b = Input(
            event_type="switch/press",
            data={"pressed": False},
            producer_id=1,
            timestamp=datetime(2024, 1, 1),
        )

        store.update(event_a)
        store.update(event_b)

        assert store.get_latest("switch/press", producer_id=0) is not None
        producer_one = store.get_latest("switch/press", producer_id=1)
        assert producer_one is not None
        assert producer_one.data == {"pressed": False}
        assert producer_one.timestamp.tzinfo is not None



    def test_state_store_snapshot_is_immutable(self) -> None:
        """Verify that StateStore.snapshot returns immutable structures. This prevents observers from corrupting stored history."""
        store = StateStore()
        store.update(Input(event_type="dial/rotate", data={"value": 5}, producer_id=0))

        snapshot = store.snapshot()
        bucket = snapshot["dial/rotate"]
        assert 0 in bucket

        try:
            cast(dict[int, Input], bucket)[1] = bucket[0]
        except TypeError:
            pass
        else:  # pragma: no cover - enforce immutability even if TypeError not raised
            raise AssertionError("snapshot bucket is mutable")



    def test_get_all_returns_read_only_mapping(self) -> None:
        """Verify that StateStore.get_all returns a read-only mapping. This ensures data integrity even when handing references to plugins."""
        store = StateStore()
        store.update(Input(event_type="dial/rotate", data={"value": 5}, producer_id=0))

        mapping = store.get_all("dial/rotate")
        assert 0 in mapping
        try:
            cast(dict[int, Input], mapping)[1] = mapping[0]
        except TypeError:
            pass
        else:  # pragma: no cover
            raise AssertionError("get_all mapping is mutable")

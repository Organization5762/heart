from datetime import datetime

from heart.peripheral import Input, StateStore


def test_state_store_tracks_latest_events_by_producer() -> None:
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


def test_state_store_snapshot_is_immutable() -> None:
    store = StateStore()
    store.update(Input(event_type="dial/rotate", data={"value": 5}, producer_id=0))

    snapshot = store.snapshot()
    bucket = snapshot["dial/rotate"]
    assert 0 in bucket

    try:
        bucket[1] = bucket[0]  # type: ignore[assignment]
    except TypeError:
        pass
    else:  # pragma: no cover - enforce immutability even if TypeError not raised
        raise AssertionError("snapshot bucket is mutable")


def test_get_all_returns_read_only_mapping() -> None:
    store = StateStore()
    store.update(Input(event_type="dial/rotate", data={"value": 5}, producer_id=0))

    mapping = store.get_all("dial/rotate")
    assert 0 in mapping
    try:
        mapping[1] = mapping[0]  # type: ignore[assignment]
    except TypeError:
        pass
    else:  # pragma: no cover
        raise AssertionError("get_all mapping is mutable")

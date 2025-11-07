import threading
import time
from typing import Any

import pytest

from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import (EventBus, EventPlaylist,
                                             EventPlaylistManager,
                                             PlaylistHandle, PlaylistStep,
                                             SequenceMatcher,
                                             double_tap_virtual_peripheral,
                                             sequence_virtual_peripheral,
                                             simultaneous_virtual_peripheral)


def test_emit_orders_callbacks_by_priority_then_fifo():
    bus = EventBus()
    order: list[str] = []

    bus.subscribe("button", lambda evt: order.append("low"), priority=0)
    bus.subscribe("button", lambda evt: order.append("mid"), priority=5)
    bus.subscribe("button", lambda evt: order.append("mid-2"), priority=5)
    bus.subscribe("button", lambda evt: order.append("high"), priority=10)

    bus.emit("button", data=None)

    assert order == ["high", "mid", "mid-2", "low"]


def test_run_on_event_decorator_registers_handler():
    bus = EventBus()
    captured: list[int] = []

    @bus.run_on_event("tick")
    def _handler(event: Input) -> None:
        captured.append(event.producer_id)

    bus.emit("tick", data="value", producer_id=42)

    assert captured == [42]


def test_subscriber_failures_do_not_block_others(caplog: pytest.LogCaptureFixture):
    bus = EventBus()
    caplog.set_level("ERROR")
    calls: list[str] = []

    def _bad(_: Input) -> None:
        raise RuntimeError("boom")

    bus.subscribe("sensor", _bad)
    bus.subscribe("sensor", lambda event: calls.append(event.event_type))

    bus.emit(Input(event_type="sensor", data={}))

    assert calls == ["sensor"]
    assert any("EventBus subscriber" in message for message in caplog.messages)


def test_emit_updates_state_store_before_callbacks():
    bus = EventBus()

    observed: list[int] = []

    def _handler(event: Input) -> None:
        entry = bus.state_store.get_latest(event.event_type, producer_id=event.producer_id)
        assert entry is not None
        observed.append(entry.producer_id)

    bus.subscribe("button", _handler)

    bus.emit("button", data={"pressed": True}, producer_id=2)

    assert observed == [2]


def test_playlist_manual_start_runs_to_completion() -> None:
    bus = EventBus()
    emitted_values: list[int] = []
    playlist_events: list[dict] = []
    stops: list[dict] = []
    completions: list[dict] = []

    bus.subscribe(
        "color.update",
        lambda event: emitted_values.append(event.data["value"]),
    )
    bus.subscribe(
        EventPlaylistManager.EVENT_EMITTED,
        lambda event: playlist_events.append(event.data),
    )
    bus.subscribe(
        EventPlaylistManager.EVENT_STOPPED,
        lambda event: stops.append(event.data),
    )

    playlist = EventPlaylist(
        name="cycle",
        steps=[
            PlaylistStep(
                event_type="color.update",
                data={"value": 7},
                offset=0.0,
                repeat=3,
                interval=0.01,
                producer_id=5,
            )
        ],
        completion_event_type="color.cycle.complete",
        metadata={"mode": "test"},
    )
    handle: PlaylistHandle = bus.playlists.register(playlist)

    bus.subscribe(
        "color.cycle.complete",
        lambda event: completions.append(event.data),
    )

    run_id = bus.playlists.start(handle)
    assert bus.playlists.join(run_id, timeout=1.0)

    assert emitted_values == [7, 7, 7]
    assert [item["repeat_index"] for item in playlist_events] == [0, 1, 2]
    assert all(item["data"] == {"value": 7} for item in playlist_events)
    assert stops and stops[0]["reason"] == "completed"
    assert stops[0]["playlist_metadata"] == {"mode": "test"}
    assert completions and completions[0]["playlist_id"] == run_id
    assert completions[0]["playlist_metadata"] == {"mode": "test"}


def test_playlist_trigger_interrupted_by_event() -> None:
    bus = EventBus()
    created_events: list[dict] = []
    emitted_events: list[dict] = []
    stop_events: list[dict] = []

    created_ready = threading.Event()
    emitted_twice = threading.Event()

    bus.subscribe(
        EventPlaylistManager.EVENT_CREATED,
        lambda event: (created_events.append(event.data), created_ready.set()),
    )
    bus.subscribe(
        EventPlaylistManager.EVENT_EMITTED,
        lambda event: (
            emitted_events.append(event.data),
            emitted_twice.set()
            if len(emitted_events) >= 2
            else None,
        ),
    )
    bus.subscribe(
        EventPlaylistManager.EVENT_STOPPED,
        lambda event: stop_events.append(event.data),
    )

    playlist = EventPlaylist(
        name="interruptible",
        steps=[
            PlaylistStep(
                event_type="color.update",
                data={"value": 1},
                offset=0.0,
                repeat=10,
                interval=0.05,
            )
        ],
        trigger_event_type="start.sequence",
        interrupt_events=("stop.sequence",),
        metadata={"mode": "interrupt"},
    )
    bus.playlists.register(playlist)

    bus.emit("start.sequence", data={"begin": True})
    assert created_ready.wait(timeout=1.0)
    run_id = created_events[0]["playlist_id"]

    # Wait for at least two emissions before interrupting.
    assert emitted_twice.wait(timeout=1.0)
    bus.emit("stop.sequence", data={"reason": "test"})

    assert bus.playlists.join(run_id, timeout=1.0)

    assert stop_events and stop_events[0]["reason"] == "interrupted"
    interrupt_data = stop_events[0]["interrupt_event"]
    assert interrupt_data["event_type"] == "stop.sequence"
    assert interrupt_data["data"] == {"reason": "test"}
    assert created_events[0]["trigger_event"]["data"] == {"begin": True}
    assert created_events[0]["playlist_metadata"] == {"mode": "interrupt"}
    assert emitted_events
    assert len(emitted_events) < 10


@pytest.mark.parametrize(
    "data_factory, mutator",
    [
        (
            lambda: {"value": 0},
            lambda event: event.data.__setitem__(
                "value", event.data["value"] + 1
            ),
        ),
        (
            lambda: [1, 2],
            lambda event: event.data.append("mutated"),
        ),
        (
            lambda: ("base", {"count": 0}),
            lambda event: event.data[1].__setitem__(
                "count", event.data[1]["count"] + 1
            ),
        ),
    ],
)
def test_playlist_step_payloads_are_isolated(data_factory, mutator) -> None:
    bus = EventBus()
    mutated_payloads: list[Any] = []
    telemetry_snapshots: list[Any] = []

    bus.subscribe(
        "mutable.event",
        lambda event: (mutator(event), mutated_payloads.append(event.data)),
    )
    bus.subscribe(
        EventPlaylistManager.EVENT_EMITTED,
        lambda event: telemetry_snapshots.append(event.data["data"]),
    )

    playlist = EventPlaylist(
        name="mutable",
        steps=[
            PlaylistStep(
                event_type="mutable.event",
                data=data_factory(),
                offset=0.0,
                repeat=2,
                interval=0.01,
            )
        ],
    )
    handle = bus.playlists.register(playlist)

    run_id = bus.playlists.start(handle)
    assert bus.playlists.join(run_id, timeout=1.0)

    expected = data_factory()
    assert telemetry_snapshots == [expected, expected]
    assert len(mutated_payloads) == 2
    assert mutated_payloads[0] == mutated_payloads[1]
    assert mutated_payloads[0] != expected


def test_playlist_created_payload_mutation_does_not_affect_run() -> None:
    bus = EventBus()
    observed: list[int] = []

    bus.subscribe(
        EventPlaylistManager.EVENT_CREATED,
        lambda event: event.data["steps"][0]["data"].__setitem__("value", 99),
    )
    bus.subscribe(
        "color.update",
        lambda event: observed.append(event.data["value"]),
    )

    playlist = EventPlaylist(
        name="immutable",
        steps=[
            PlaylistStep(
                event_type="color.update",
                data={"value": 7},
                offset=0.0,
            )
        ],
    )
    handle = bus.playlists.register(playlist)

    run_id = bus.playlists.start(handle)
    assert bus.playlists.join(run_id, timeout=1.0)

    assert observed == [7]


def test_virtual_double_tap_emits_enriched_payload() -> None:
    bus = EventBus()
    captured: list[dict] = []

    definition = double_tap_virtual_peripheral(
        "button.press",
        output_event_type="button.double_tap",
        window=0.5,
        metadata={"gesture": "double"},
    )
    bus.virtual_peripherals.register(definition)

    bus.subscribe(
        "button.double_tap",
        lambda event: captured.append(event.data),
    )

    bus.emit("button.press", data={"state": "down"}, producer_id=1)
    bus.emit("button.press", data={"state": "down"}, producer_id=1)

    assert captured
    payload = captured[0]
    assert payload["virtual_peripheral"]["name"] == definition.name
    assert payload["virtual_peripheral"]["metadata"] == {"gesture": "double"}
    assert [item["data"] for item in payload["events"]] == [
        {"state": "down"},
        {"state": "down"},
    ]

    captured.clear()
    time.sleep(0.6)
    bus.emit("button.press", data={"state": "down"}, producer_id=1)
    time.sleep(0.6)
    bus.emit("button.press", data={"state": "down"}, producer_id=1)
    assert not captured


def test_virtual_simultaneous_detector_requires_distinct_producers() -> None:
    bus = EventBus()
    detected: list[dict] = []

    bus.virtual_peripherals.register(
        simultaneous_virtual_peripheral(
            "sensor.trigger",
            output_event_type="sensor.combo",
            window=0.05,
            required_sources=2,
        )
    )

    bus.subscribe("sensor.combo", lambda event: detected.append(event.data))

    bus.emit("sensor.trigger", data={"value": 1}, producer_id=1)
    time.sleep(0.005)
    bus.emit("sensor.trigger", data={"value": 2}, producer_id=2)

    assert detected
    payload = detected[0]
    producers = {item["producer_id"] for item in payload["events"]}
    assert producers == {1, 2}

    detected.clear()
    time.sleep(0.06)
    bus.emit("sensor.trigger", data={"value": 3}, producer_id=1)
    bus.emit("sensor.trigger", data={"value": 4}, producer_id=1)
    assert not detected


def test_sequence_virtual_peripheral_detects_konami_code() -> None:
    bus = EventBus()
    detected: list[dict] = []

    konami = [
        "up",
        "up",
        "down",
        "down",
        "left",
        "right",
        "left",
        "right",
        "b",
        "a",
    ]

    matchers = [
        SequenceMatcher(
            "button.press",
            predicate=lambda event, expected=direction: event.data["code"]
            == expected,
        )
        for direction in konami
    ]

    definition = sequence_virtual_peripheral(
        name="konami.listener",
        matchers=matchers,
        output_event_type="konami.activated",
        timeout=1.0,
        metadata={"combo": "konami"},
    )
    bus.virtual_peripherals.register(definition)

    bus.subscribe(
        "konami.activated",
        lambda event: detected.append(event.data),
    )

    bus.emit("button.press", data={"code": "up"}, producer_id=7)
    bus.emit("button.press", data={"code": "left"}, producer_id=7)
    assert not detected

    for direction in konami:
        bus.emit("button.press", data={"code": direction}, producer_id=7)

    assert detected
    payload = detected[0]
    assert payload["virtual_peripheral"]["name"] == "konami.listener"
    assert payload["virtual_peripheral"]["metadata"] == {"combo": "konami"}
    assert [item["data"]["code"] for item in payload["sequence"]] == konami

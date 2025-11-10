import threading
import time
from typing import Any, Mapping, cast

import pytest

from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import (EventBus, EventPlaylist,
                                             EventPlaylistManager,
                                             PlaylistHandle, PlaylistStep,
                                             SequenceMatcher,
                                             VirtualPeripheralContext,
                                             VirtualPeripheralDefinition,
                                             double_tap_virtual_peripheral,
                                             gated_mirror_virtual_peripheral,
                                             gated_playlist_virtual_peripheral,
                                             sequence_virtual_peripheral,
                                             simultaneous_virtual_peripheral)


class TestPeripheralEventBus:
    """Group Peripheral Event Bus tests so peripheral event bus behaviour stays reliable. This preserves confidence in peripheral event bus for end-to-end scenarios."""

    def test_emit_orders_callbacks_by_priority_then_fifo(self):
        """Verify that emit orders callbacks by priority then fifo. This guarantees deterministic fan-out so critical handlers run first."""
        bus = EventBus()
        order: list[str] = []

        bus.subscribe("button", lambda evt: order.append("low"), priority=0)
        bus.subscribe("button", lambda evt: order.append("mid"), priority=5)
        bus.subscribe("button", lambda evt: order.append("mid-2"), priority=5)
        bus.subscribe("button", lambda evt: order.append("high"), priority=10)

        bus.emit("button", data=None)

        assert order == ["high", "mid", "mid-2", "low"]



    def test_run_on_event_decorator_registers_handler(self):
        """Verify that run_on_event decorator registers handler. This keeps the decorator API trustworthy for peripheral integrations."""
        bus = EventBus()
        captured: list[int] = []

        @bus.run_on_event("tick")
        def _handler(event: Input) -> None:
            captured.append(event.producer_id)

        bus.emit("tick", data="value", producer_id=42)

        assert captured == [42]



    def test_subscriber_failures_do_not_block_others(self, caplog: pytest.LogCaptureFixture):
        """Verify that subscriber failures do not block others. This ensures one buggy subscriber cannot stall the event pipeline."""
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



    def test_emit_updates_state_store_before_callbacks(self):
        """Verify that emit updates state store before callbacks. This guarantees observers see consistent state snapshots."""
        bus = EventBus()

        observed: list[int] = []

        def _handler(event: Input) -> None:
            entry = bus.state_store.get_latest(event.event_type, producer_id=event.producer_id)
            assert entry is not None
            observed.append(entry.producer_id)

        bus.subscribe("button", _handler)

        bus.emit("button", data={"pressed": True}, producer_id=2)

        assert observed == [2]



    def test_playlist_manual_start_runs_to_completion(self) -> None:
        """Verify that playlist manual start runs to completion. This proves automation sequences finish reliably when triggered programmatically."""
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



    def test_playlist_trigger_interrupted_by_event(self) -> None:
        """Verify that playlist trigger interrupted by event. This shows playlists respond promptly to stop signals for safety."""
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



    def test_virtual_peripheral_definitions_bind_resources(self) -> None:
        """Verify that virtual peripheral definitions bind resources. This keeps dependency injection sane so virtual peripherals remain testable."""
        bus = EventBus()
        captured: dict[str, Any] = {}
        handled: list[int] = []

        class DummyVirtualPeripheral:
            def __init__(self, context: VirtualPeripheralContext) -> None:
                self._context = context
                captured["context"] = context
                captured["foo"] = context.get_resource("foo")
                captured["combo"] = context.get_resource("combo")
                captured["state_store"] = context.resources["state_store"]

            def handle(self, event: Input) -> None:
                handled.append(self._context.get_resource("foo"))

            def shutdown(self) -> None:
                captured["shutdown"] = True

        definition = VirtualPeripheralDefinition(
            name="dummy.resources",
            event_types=("button.press",),
            factory=DummyVirtualPeripheral,
            resources={
                "foo": lambda ctx: 41,
                "combo": lambda ctx: ctx.get_resource("foo") + 1,
                "state_store": lambda ctx: ctx.state_store,
            },
        )

        handle = bus.virtual_peripherals.register(definition)
        bus.emit("button.press", data={})

        assert handled == [41]
        assert captured["foo"] == 41
        assert captured["combo"] == 42
        assert captured["state_store"] is bus.state_store

        resources = bus.virtual_peripherals.list_definitions()[handle.peripheral_id].resources
        assert resources is not None
        with pytest.raises(TypeError):
            cast(dict[str, Any], resources)["foo"] = 99

        dummy_context = captured["context"]
        with pytest.raises(TypeError):
            cast(dict[str, Any], dummy_context.resources)["foo"] = 5
        with pytest.raises(KeyError):
            dummy_context.get_resource("missing")

        bus.virtual_peripherals.remove(handle)
        assert captured.get("shutdown") is True


    def test_gated_playlist_virtual_peripheral_runs_playlist(self) -> None:
        """Verify that gated playlist virtual peripheral runs playlist. This confirms event-driven lighting cues respond to gate signals."""
        bus = EventBus()
        outputs: list[int] = []
        created_payloads: list[Mapping[str, Any]] = []
        stop_payloads: list[Mapping[str, Any]] = []

        created_ready = threading.Event()
        stopped_ready = threading.Event()

        bus.subscribe(
            "color.update",
            lambda event: outputs.append(event.data["value"]),
        )
        bus.subscribe(
            EventPlaylistManager.EVENT_CREATED,
            lambda event: (created_payloads.append(event.data), created_ready.set()),
        )
        bus.subscribe(
            EventPlaylistManager.EVENT_STOPPED,
            lambda event: (stop_payloads.append(event.data), stopped_ready.set()),
        )

        playlist = EventPlaylist(
            name="flash",
            steps=[
                PlaylistStep(
                    event_type="color.update",
                    data={"value": 1},
                    offset=0.0,
                    repeat=2,
                    interval=0.01,
                    producer_id=7,
                )
            ],
            metadata={"mode": "flash"},
        )

        definition = gated_playlist_virtual_peripheral(
            ("button.press",),
            playlist=playlist,
            name="button.flash",
        )
        bus.virtual_peripherals.register(definition)

        bus.emit("button.press", data={"intensity": 3}, producer_id=2)

        assert created_ready.wait(timeout=1.0)
        run_id = created_payloads[0]["playlist_id"]
        assert bus.playlists.join(run_id, timeout=1.0)
        assert stopped_ready.wait(timeout=1.0)

        assert outputs == [1, 1]
        assert created_payloads[0]["trigger_event"]["data"] == {"intensity": 3}
        assert stop_payloads[0]["reason"] == "completed"



    def test_gated_playlist_virtual_peripheral_cancels_previous_runs(self) -> None:
        """Verify that gated playlist virtual peripheral cancels previous runs. This prevents overlapping animations that could overload devices."""
        bus = EventBus()
        created_payloads: list[Mapping[str, Any]] = []
        stop_payloads: list[Mapping[str, Any]] = []

        first_created = threading.Event()
        second_created = threading.Event()
        first_stopped = threading.Event()
        second_stopped = threading.Event()

        def handle_created(event: Input) -> None:
            created_payloads.append(event.data)
            if len(created_payloads) == 1:
                first_created.set()
            elif len(created_payloads) == 2:
                second_created.set()

        def handle_stopped(event: Input) -> None:
            stop_payloads.append(event.data)
            if len(stop_payloads) == 1:
                first_stopped.set()
            elif len(stop_payloads) == 2:
                second_stopped.set()

        bus.subscribe(EventPlaylistManager.EVENT_CREATED, handle_created)
        bus.subscribe(EventPlaylistManager.EVENT_STOPPED, handle_stopped)

        playlist = EventPlaylist(
            name="long",
            steps=[
                PlaylistStep(
                    event_type="color.update",
                    data={"value": 9},
                    offset=0.0,
                    repeat=5,
                    interval=0.05,
                )
            ],
        )

        definition = gated_playlist_virtual_peripheral(
            ("button.press",),
            playlist=playlist,
            cancel_active_runs=True,
        )
        bus.virtual_peripherals.register(definition)

        bus.emit("button.press", data={"sequence": 1})
        assert first_created.wait(timeout=1.0)
        assert created_payloads[0]["trigger_event"]["data"] == {"sequence": 1}

        bus.emit("button.press", data={"sequence": 2})
        assert second_created.wait(timeout=1.0)
        assert created_payloads[1]["trigger_event"]["data"] == {"sequence": 2}

        first_run = created_payloads[0]["playlist_id"]
        second_run = created_payloads[1]["playlist_id"]

        assert first_stopped.wait(timeout=1.0)
        assert stop_payloads[0]["reason"] == "cancelled"
        assert bus.playlists.join(first_run, timeout=1.0)

        assert second_stopped.wait(timeout=1.0)
        assert stop_payloads[1]["reason"] == "completed"
        assert bus.playlists.join(second_run, timeout=1.0)


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
    def test_playlist_step_payloads_are_isolated(self, data_factory, mutator) -> None:
        """Verify that playlist step payloads are isolated. This shields reusable playlists from subscriber mutations."""
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



    def test_playlist_created_payload_mutation_does_not_affect_run(self) -> None:
        """Verify that playlist created payload mutation does not affect run. This demonstrates emitted telemetry is isolated from observers."""
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



    def test_virtual_double_tap_emits_enriched_payload(self) -> None:
        """Verify that virtual double tap emits enriched payload. This powers advanced gesture detection for richer interactions."""
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



    def test_virtual_simultaneous_detector_requires_distinct_producers(self) -> None:
        """Verify that virtual simultaneous detector requires distinct producers. This prevents false positives when a single sensor fires rapidly."""
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



    def test_sequence_virtual_peripheral_detects_konami_code(self) -> None:
        """Verify that sequence virtual peripheral detects konami code. This showcases complex input macros built from primitive events."""
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



    def test_gated_mirror_virtual_peripheral_re_emits_with_virtual_metadata(self) -> None:
        """Verify that gated mirror virtual peripheral re-emits with virtual metadata. This keeps mirrored streams attributed to their virtual origin."""
        bus = EventBus()
        captured: list[Input] = []

        definition = gated_mirror_virtual_peripheral(
            "microphone.gated",
            gate_event_type="button.toggle",
            mirror_event_types="peripheral.microphone.level",
            output_producer_id=99,
            metadata={"mode": "gated"},
        )
        bus.virtual_peripherals.register(definition)

        bus.subscribe(
            "peripheral.microphone.level",
            lambda event: captured.append(event),
        )

        # Events should be ignored while the gate is off.
        bus.emit(
            "peripheral.microphone.level",
            data={"rms": 0.2, "peak": 0.3},
            producer_id=7,
        )
        assert not [event for event in captured if event.producer_id == 99]

        # Enable the gate and verify mirrored events include metadata.
        bus.emit("button.toggle", data={"pressed": True}, producer_id=1)
        bus.emit(
            "peripheral.microphone.level",
            data={"rms": 0.4, "peak": 0.5},
            producer_id=7,
        )

        mirrored = [event for event in captured if event.producer_id == 99]
        assert mirrored
        mirrored_event = mirrored[-1]
        assert mirrored_event.data["rms"] == 0.4
        assert mirrored_event.data["virtual_peripheral"]["name"] == "microphone.gated"
        assert mirrored_event.data["virtual_peripheral"]["metadata"] == {"mode": "gated"}

        # Disable the gate and ensure mirroring stops.
        bus.emit("button.toggle", data={"pressed": False}, producer_id=1)
        bus.emit(
            "peripheral.microphone.level",
            data={"rms": 0.6, "peak": 0.7},
            producer_id=7,
        )

        later_mirrored = [event for event in captured if event.producer_id == 99]
        assert later_mirrored == mirrored



    def test_gated_mirror_virtual_peripheral_supports_composed_conditions(self) -> None:
        """Verify that gated mirror virtual peripheral supports composed conditions. This enables complex gating logic for nuanced control flows."""
        bus = EventBus()
        captured: list[Input] = []

        def _truthy(data: Any) -> bool:
            if isinstance(data, Mapping):
                for key in ("pressed", "state", "enabled", "value", "active"):
                    if key in data:
                        return bool(data[key])
                return bool(data)
            return bool(data)

        def _predicate(context, event: Input) -> bool:
            button_entry = context.state_store.get_latest("button.toggle")
            combo_entry = context.state_store.get_latest("combo.activated")
            button_active = _truthy(button_entry.data) if button_entry else False
            combo_active = _truthy(combo_entry.data) if combo_entry else False
            return button_active and combo_active

        definition = gated_mirror_virtual_peripheral(
            "microphone.combo",
            gate_event_type=("button.toggle", "combo.activated"),
            mirror_event_types="peripheral.microphone.level",
            output_producer_id=101,
            gate_predicate=_predicate,
        )
        bus.virtual_peripherals.register(definition)

        bus.subscribe(
            "peripheral.microphone.level",
            lambda event: captured.append(event),
        )

        def _mirrored() -> list[Input]:
            return [event for event in captured if event.producer_id == 101]

        bus.emit("peripheral.microphone.level", data={"rms": 0.1}, producer_id=7)
        assert not _mirrored()

        bus.emit("combo.activated", data={"active": True}, producer_id=3)
        bus.emit("peripheral.microphone.level", data={"rms": 0.2}, producer_id=7)
        assert not _mirrored()

        bus.emit("button.toggle", data={"pressed": True}, producer_id=1)
        bus.emit("peripheral.microphone.level", data={"rms": 0.3}, producer_id=7)
        mirrored = _mirrored()
        assert mirrored and mirrored[-1].data["rms"] == 0.3

        bus.emit("combo.activated", data={"active": False}, producer_id=3)
        bus.emit("peripheral.microphone.level", data={"rms": 0.4}, producer_id=7)
        assert mirrored == _mirrored()

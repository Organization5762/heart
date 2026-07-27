from __future__ import annotations

import gc
import time
import tracemalloc
from datetime import datetime, timezone

import pygame
from PIL import Image

from heart.device.beats.websocket import ControlMessage
from heart.peripheral.core.input import (BrowseIntent, GamepadAxis,
                                         GamepadButton, GamepadDpadValue,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         InputDebugStage, KeyboardSnapshot)
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.runtime.peripheral_runtime import (INPUT_DEBUG_STAGE_TAG,
                                              INPUT_DEBUG_STREAM_TAG,
                                              PeripheralRuntime,
                                              save_phone_photo)

EMPTY_KEYBOARD = KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)


def _navigation_tuple(intent) -> tuple[str, int, str]:
    return (
        type(intent).__name__,
        intent.step if isinstance(intent, BrowseIntent) else 0,
        intent.source,
    )


def _gamepad_event(snapshot: GamepadSnapshot) -> GamepadSnapshotEvent:
    return GamepadSnapshotEvent(joystick_id=0, snapshot=snapshot)


class _WebSocketStub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []
        self.control_handler = None

    def send(self, kind: str, payload: object) -> None:
        self.sent.append((kind, payload))

    def set_control_handler(self, handler) -> None:
        self.control_handler = handler


class _TemporaryRendererLoop:
    def __init__(self) -> None:
        self.clear_count = 0
        self.floating_emojis: list[str] = []

    def clear_temporary_renderer(self) -> None:
        self.clear_count += 1

    def present_floating_emoji(self, emoji: str) -> None:
        self.floating_emojis.append(emoji)


class TestPeripheralRuntimeStreaming:
    """Exercise peripheral runtime stream bridging so Beats receives structured reconnect-safe peripheral payloads."""

    def test_configure_streaming_skips_websocket_when_beats_forwarding_is_disabled(
        self, monkeypatch
    ) -> None:
        """Verify default runtime startup avoids booting the Beats websocket so plain sessions do not open an unused server."""

        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.forward_to_beats_app",
            classmethod(lambda cls: False),
        )
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.beats_websocket_enabled",
            classmethod(lambda cls: False),
        )

        def _unexpected_websocket() -> object:
            raise AssertionError(
                "WebSocket should not be constructed without Beats forwarding"
            )

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime._build_websocket",
            _unexpected_websocket,
        )

        runtime.configure_streaming()

    def test_configure_streaming_starts_websocket_for_control_server(
        self, monkeypatch
    ) -> None:
        """Verify phone controls can start the Beats websocket without switching the runtime to streamed display output."""

        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.forward_to_beats_app",
            classmethod(lambda cls: False),
        )
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.beats_websocket_enabled",
            classmethod(lambda cls: True),
        )
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime._build_websocket",
            lambda: websocket,
        )

        runtime.configure_streaming()

        assert websocket.control_handler is not None

    def test_configure_streaming_emits_peripheral_envelopes(self, monkeypatch) -> None:
        """Verify debug tap events are wrapped as peripheral payloads so the Beats websocket can replay and decode them after reconnects."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.stream_beats_input_debug",
            classmethod(lambda cls: True),
        )

        runtime.configure_streaming(websocket=websocket)
        manager.input_io.debug_tap.publish(
            stage=InputDebugStage.RAW,
            stream_name="switch.tick",
            source_id="switch-1",
            payload={
                "rotation": 1,
                "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
        )

        assert len(websocket.sent) == 1
        kind, envelope = websocket.sent[0]
        assert kind == "peripheral"
        assert envelope.peripheral_info.id == "switch-1"
        assert envelope.peripheral_info.tags[0].name == INPUT_DEBUG_STAGE_TAG
        assert envelope.peripheral_info.tags[0].variant == InputDebugStage.RAW.value
        assert envelope.peripheral_info.tags[1].name == INPUT_DEBUG_STREAM_TAG
        assert envelope.peripheral_info.tags[1].variant == "switch.tick"
        assert envelope.data["stream_name"] == "switch.tick"
        assert envelope.data["source_id"] == "switch-1"

    def test_configure_streaming_leaves_input_debug_off_by_default(self) -> None:
        """Keep Beats frame/control streaming lightweight unless debug telemetry is explicitly requested."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()

        runtime.configure_streaming(websocket=websocket)
        manager.input_io.debug_tap.publish(
            stage=InputDebugStage.RAW,
            stream_name="switch.tick",
            source_id="switch-1",
            payload={"rotation": 1},
        )

        assert websocket.control_handler is not None
        assert websocket.sent == []

    def test_configure_streaming_maps_control_commands_into_navigation_injections(
        self,
    ) -> None:
        """Verify websocket control commands inject navigation intents so Beats controls can drive runtime navigation through the shared logical stream."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(
            lambda intent: observed.append(_navigation_tuple(intent))
        )

        try:
            runtime.configure_streaming(websocket=websocket)
            assert websocket.control_handler is not None

            websocket.control_handler(ControlMessage(command="browse", browse_step=2))
            websocket.control_handler(ControlMessage(command="activate"))
            websocket.control_handler(ControlMessage(command="alternate_activate"))

            assert observed == []
            runtime._drain_control_messages()
        finally:
            subscription.dispose()

        assert observed == [
            ("BrowseIntent", 2, "beats.control.browse"),
            ("ActivateIntent", 0, "beats.control.activate"),
            ("AlternateActivateIntent", 0, "beats.control.alternate"),
        ]

    def test_configure_streaming_maps_sensor_control_commands_into_external_hub(
        self,
    ) -> None:
        """Verify websocket sensor commands update the external hub so Beats-side controls become runtime-owned sensor values."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()
        observed: list[Acceleration | None] = []
        subscription = (
            manager.input_io.external_sensors.observable_acceleration().subscribe(
                observed.append
            )
        )

        try:
            runtime.configure_streaming(websocket=websocket)
            assert websocket.control_handler is not None

            websocket.control_handler(
                ControlMessage(
                    command="sensor_update",
                    sensor_key="accelerometer:debug:z",
                    sensor_value=12.5,
                )
            )
            websocket.control_handler(
                ControlMessage(
                    command="sensor_update",
                    sensor_key="accelerometer:debug:z",
                    clear=True,
                )
            )

            runtime._drain_control_messages()
        finally:
            subscription.dispose()

        assert Acceleration(x=0.0, y=0.0, z=12.5) in observed
        assert observed[-1] is None

    def test_poll_maps_one_sampled_gamepad_snapshot_to_navigation(
        self,
        monkeypatch,
    ) -> None:
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        samples = iter(
            (
                (
                    _gamepad_event(
                        GamepadSnapshot(
                            connected=True,
                            identifier="controller",
                            dpad=GamepadDpadValue(x=1),
                            buttons={GamepadButton.SOUTH: True},
                        )
                    ),
                ),
                (
                    _gamepad_event(
                        GamepadSnapshot(
                            connected=True,
                            identifier="controller",
                            buttons={GamepadButton.NORTH: True},
                        )
                    ),
                ),
            )
        )
        monkeypatch.setattr(
            manager.input_io,
            "poll",
            lambda: (EMPTY_KEYBOARD, next(samples)),
        )
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(
            lambda intent: observed.append(_navigation_tuple(intent))
        )

        try:
            runtime.poll()
            runtime.poll()
        finally:
            subscription.dispose()

        assert observed == [
            ("BrowseIntent", 1, "gamepad.dpad"),
            ("ActivateIntent", 0, "gamepad.0.south"),
            ("AlternateActivateIntent", 0, "gamepad.0.north"),
        ]

    def test_poll_maps_keyboard_edges_to_navigation(self, monkeypatch) -> None:
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        snapshots = iter(
            (
                KeyboardSnapshot(
                    pressed_keys=frozenset({pygame.K_RIGHT, pygame.K_DOWN}),
                    timestamp_ms=1.0,
                ),
                KeyboardSnapshot(
                    pressed_keys=frozenset({pygame.K_RIGHT, pygame.K_DOWN}),
                    timestamp_ms=1.0,
                ),
                KeyboardSnapshot(
                    pressed_keys=frozenset(),
                    timestamp_ms=2.0,
                ),
                KeyboardSnapshot(
                    pressed_keys=frozenset({pygame.K_LEFT, pygame.K_UP}),
                    timestamp_ms=3.0,
                ),
            )
        )
        monkeypatch.setattr(
            manager.input_io,
            "poll",
            lambda: (next(snapshots), ()),
        )
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(
            lambda intent: observed.append(_navigation_tuple(intent))
        )

        try:
            for _ in range(4):
                runtime.poll()
        finally:
            subscription.dispose()

        assert observed == [
            ("BrowseIntent", 1, "keyboard.right"),
            ("ActivateIntent", 0, "keyboard.down"),
            ("BrowseIntent", -1, "keyboard.left"),
            ("AlternateActivateIntent", 0, "keyboard.up"),
        ]

    def test_poll_does_not_consume_renderer_local_tap_buttons(
        self,
        monkeypatch,
    ) -> None:
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        event = _gamepad_event(
            GamepadSnapshot(
                connected=True,
                identifier="controller",
                buttons={
                    GamepadButton.WEST: True,
                    GamepadButton.L3: True,
                },
                tapped_buttons=frozenset({GamepadButton.WEST, GamepadButton.L3}),
                axes={GamepadAxis.LEFT_X: 1.0},
            )
        )
        monkeypatch.setattr(
            manager.input_io,
            "poll",
            lambda: (EMPTY_KEYBOARD, (event,)),
        )
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(observed.append)

        try:
            runtime.poll()
        finally:
            subscription.dispose()

        assert observed == []

    def test_poll_latches_sampled_dpad_until_centered(self, monkeypatch) -> None:
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        samples = iter(
            (
                GamepadSnapshot(
                    connected=True,
                    identifier="controller",
                    dpad=GamepadDpadValue(x=1),
                ),
                GamepadSnapshot(
                    connected=True,
                    identifier="controller",
                    dpad=GamepadDpadValue(x=1),
                ),
                GamepadSnapshot(
                    connected=True,
                    identifier="controller",
                    dpad=GamepadDpadValue(),
                ),
                GamepadSnapshot(
                    connected=True,
                    identifier="controller",
                    dpad=GamepadDpadValue(),
                ),
                GamepadSnapshot(
                    connected=True,
                    identifier="controller",
                    dpad=GamepadDpadValue(x=-1),
                ),
            )
        )
        monkeypatch.setattr(
            manager.input_io,
            "poll",
            lambda: (EMPTY_KEYBOARD, (_gamepad_event(next(samples)),)),
        )
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(
            lambda intent: observed.append(_navigation_tuple(intent))
        )

        try:
            for _ in range(5):
                runtime.poll()
        finally:
            subscription.dispose()

        assert observed == [
            ("BrowseIntent", 1, "gamepad.dpad"),
            ("BrowseIntent", -1, "gamepad.dpad"),
        ]

    def test_poll_handles_gamepad_before_main_thread_drain(self, monkeypatch) -> None:
        """Keep queued renderer graph work from sitting in front of direct input polling."""

        call_order: list[str] = []
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        event = _gamepad_event(
            GamepadSnapshot(
                connected=True,
                identifier="controller",
                buttons={GamepadButton.SOUTH: True},
            )
        )

        def poll():
            call_order.append("sample")
            return EMPTY_KEYBOARD, (event,)

        def drain_main_thread_queue(*, max_items: int | None = None) -> int:
            call_order.append(f"drain:{max_items}")
            return 0

        monkeypatch.setattr(manager.input_io, "poll", poll)
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.drain_main_thread_queue",
            drain_main_thread_queue,
        )
        observed = []
        subscription = manager.input_io.navigation.intents.subscribe(
            lambda intent: observed.append(_navigation_tuple(intent))
        )

        try:
            runtime.poll()
        finally:
            subscription.dispose()

        assert call_order == ["sample", "drain:64"]
        assert observed == [
            ("ActivateIntent", 0, "gamepad.0.south"),
        ]

    def test_poll_control_path_memory_stays_flat_after_warmup(
        self,
        monkeypatch,
    ) -> None:
        """Probe the hot runtime poll path so queued controls cannot accumulate per tick."""

        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        monkeypatch.setattr(
            manager.input_io,
            "poll",
            lambda: (EMPTY_KEYBOARD, ()),
        )
        samples: list[tuple[int, int]] = []
        start = time.perf_counter()
        tracemalloc.start()
        try:
            for step in range(1, 10_001):
                runtime._handle_control_message(
                    ControlMessage(command="browse", browse_step=1)
                )
                runtime.poll()
                if step in {1_000, 5_000, 10_000}:
                    gc.collect()
                    current, _peak = tracemalloc.get_traced_memory()
                    samples.append((step, current))
        finally:
            tracemalloc.stop()
        elapsed_seconds = time.perf_counter() - start

        steady_values = [current for _step, current in samples[1:]]
        assert max(steady_values) - min(steady_values) <= 8_192
        assert elapsed_seconds <= 5.0
        assert runtime._control_messages.empty()

    def test_image_clear_control_clears_temporary_renderer(self, monkeypatch) -> None:
        """Verify image clear controls remove a transient phone image instead of leaving stale artwork on screen."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()
        loop = _TemporaryRendererLoop()
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.get_active_game_loop",
            lambda: loop,
        )

        runtime.configure_streaming(websocket=websocket)
        assert websocket.control_handler is not None

        websocket.control_handler(ControlMessage(command="image_update", clear=True))
        runtime._drain_control_messages()

        assert loop.clear_count == 1

    def test_emoji_control_presents_floating_overlay(self, monkeypatch) -> None:
        """Verify emoji controls are layered through the active loop instead of replacing the current renderer."""
        manager = PeripheralManager()
        runtime = PeripheralRuntime(manager)
        websocket = _WebSocketStub()
        loop = _TemporaryRendererLoop()
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.get_active_game_loop",
            lambda: loop,
        )

        runtime.configure_streaming(websocket=websocket)
        assert websocket.control_handler is not None

        websocket.control_handler(ControlMessage(command="emoji_update", emoji="heart"))
        runtime._drain_control_messages()

        assert loop.floating_emojis == ["heart"]
        assert loop.clear_count == 0

    def test_save_phone_photo_writes_png_to_configured_directory(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        """Verify phone photos persist on the runtime host so Pi sessions keep captured images."""
        monkeypatch.setenv("HEART_PHONE_PHOTO_DIR", str(tmp_path))
        image = Image.new("RGBA", (2, 2), (255, 0, 0, 255))

        saved_path = save_phone_photo(image)

        assert saved_path.parent == tmp_path
        assert saved_path.name.startswith("phone-photo-")
        assert saved_path.suffix == ".png"
        with Image.open(saved_path) as saved_image:
            assert saved_image.size == (2, 2)

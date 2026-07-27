"""Validate the graph stream input controller, view, and profile contracts."""

from __future__ import annotations

import json
from typing import Any, cast

import pygame
import pytest
from manyfold import ConstantNode, Graph, Subscribable
from manyfold.architecture import NewValues, PubSubObservable

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Input, Peripheral, PeripheralInfo
from heart.peripheral.core.input import (AccelerometerDebugProfile,
                                         BrowseIntent, ExternalSensorHub,
                                         FrameTick, FrameTickController,
                                         GamepadAxis, GamepadButton,
                                         GamepadController, GamepadDpadValue,
                                         GamepadSnapshot, GamepadSnapshotEvent,
                                         GamepadStickValue, InputDebugStage,
                                         InputDebugTap, InputIO,
                                         KeyboardController, KeyboardSnapshot,
                                         MandelbrotControlProfile,
                                         SetOrientationCommand,
                                         ToggleDebugCommand)
from heart.peripheral.core.input.accelerometer import (
    ACCELERATION_ROUTE, DEBUG_ACCELERATION_ROUTE, _debug_acceleration_stream)
from heart.peripheral.core.input.debug import InputDebugNode
from heart.peripheral.core.input.peripheral_inputs import \
    PERIPHERAL_INPUT_DISPATCH_STREAM
from heart.peripheral.core.input.streams import average_by_frame_window
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.streams import runtime_route
from heart.peripheral.gamepad import Gamepad, GamepadIdentifier
from heart.peripheral.keyboard import (KeyboardEvent, KeyHeldEvent,
                                       KeyPressedEvent, KeyReleasedEvent,
                                       KeyState)
from heart.peripheral.sensor import Acceleration, FakeAccelerometer
from heart.peripheral.switch import BaseSwitch, SwitchState


class _StubClock:
    def __init__(self, elapsed_ms: int, fps: float) -> None:
        self._elapsed_ms = elapsed_ms
        self._fps = fps

    def get_time(self) -> int:
        return self._elapsed_ms

    def get_fps(self) -> float:
        return self._fps


class _ConfigurationLoaderStub:
    registry: object = object()

    def load(self) -> PeripheralConfiguration:
        return PeripheralConfiguration(detectors=(), graph_nodes=())


class _NoopSubscription:
    def dispose(self) -> None:
        pass


class _SwitchProbe(BaseSwitch):
    def __init__(
        self,
        stream: NewValues[SwitchState],
        source_id: str = "switch:test",
    ) -> None:
        super().__init__()
        self._stream = stream
        self._source_id = source_id

    def _event_stream(self) -> Subscribable[SwitchState]:
        return self._stream

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(id=self._source_id)


class _JoystickProbe:
    def __init__(
        self,
        *,
        name: str = "8BitDo Lite 2",
        buttons: dict[int, bool] | None = None,
        axes: dict[int, float] | None = None,
        hat: tuple[int, int] = (0, 0),
    ) -> None:
        self._name = name
        self._buttons = buttons or {}
        self._axes = axes or {}
        self._hat = hat
        self.init_calls = 0
        self.quit_calls = 0

    def init(self) -> None:
        self.init_calls += 1

    def quit(self) -> None:
        self.quit_calls += 1

    def get_name(self) -> str:
        return self._name

    def get_numbuttons(self) -> int:
        if not self._buttons:
            return 0
        return max(self._buttons) + 1

    def get_numaxes(self) -> int:
        if not self._axes:
            return 0
        return max(self._axes) + 1

    def get_button(self, button_id: int) -> bool:
        return self._buttons.get(button_id, False)

    def get_axis(self, axis_id: int) -> float:
        return self._axes.get(axis_id, 0.0)

    def get_hat(self, _hat_id: int) -> tuple[int, int]:
        return self._hat


class _FailingAxisJoystickProbe(_JoystickProbe):
    def get_axis(self, axis_id: int) -> float:
        raise RuntimeError(f"axis {axis_id} failed")


class _GamepadManager:
    def __init__(self, *gamepads: Gamepad) -> None:
        self.peripherals = gamepads


def _gamepad_controller_for_joystick(
    tap: InputDebugTap, joystick: _JoystickProbe
) -> GamepadController:
    return GamepadController(
        manager=_GamepadManager(Gamepad(joystick_id=0, joystick=joystick)),
        debug_tap=tap,
    )


class _InputProbe(Peripheral[int]):
    def __init__(self, *, accepts: bool = True) -> None:
        self.accepts = accepts
        self.inputs: list[Input] = []

    def handle_input(self, input: Input) -> None:
        self.inputs.append(input)


def _keyboard_snapshot(*pressed_keys: int, timestamp_ms: float) -> KeyboardSnapshot:
    return KeyboardSnapshot(
        pressed_keys=frozenset(pressed_keys),
        timestamp_ms=timestamp_ms,
    )


def _gamepad_snapshot(
    *,
    buttons: dict[GamepadButton, bool] | None = None,
    tapped_buttons: frozenset[GamepadButton] | None = None,
    axes: dict[GamepadAxis, float] | None = None,
    dpad: GamepadDpadValue | None = None,
    timestamp_monotonic: float = 1.0,
) -> GamepadSnapshot:
    return GamepadSnapshot(
        connected=True,
        identifier="pad",
        buttons=buttons or {},
        tapped_buttons=tapped_buttons or frozenset(),
        axes=axes
        or {
            GamepadAxis.LEFT_X: 0.0,
            GamepadAxis.LEFT_Y: 0.0,
            GamepadAxis.RIGHT_X: 0.0,
            GamepadAxis.RIGHT_Y: 0.0,
            GamepadAxis.TRIGGER_LEFT: 0.0,
            GamepadAxis.TRIGGER_RIGHT: 0.0,
        },
        dpad=dpad or GamepadDpadValue(),
        timestamp_monotonic=timestamp_monotonic,
    )


def _enable_keyboard_polling(monkeypatch) -> None:
    monkeypatch.setattr(
        "heart.peripheral.core.input.keyboard.Configuration.is_pi",
        lambda: False,
    )


class TestInputDebugTap:
    """Group debug-tap tests so traced input lineage stays inspectable during runtime and tests."""

    def test_instrumented_stream_records_stage_and_lineage(self) -> None:
        """Verify instrumented streams publish trace envelopes so developers can follow input emissions across layers."""
        tap = InputDebugTap()
        observed: list[int] = []

        InputDebugNode(
            tap=tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.activate",
            source_id="navigation",
            upstream_ids=("keyboard.pressed.down",),
        ).connect(ConstantNode(7).observable()).subscribe(observed.append)

        history = tap.snapshot()

        assert observed == [7]
        assert len(history) == 1
        assert history[0].stage is InputDebugStage.LOGICAL
        assert history[0].stream_name == "navigation.activate"
        assert history[0].source_id == "navigation"
        assert history[0].upstream_ids == ("keyboard.pressed.down",)
        assert history[0].payload == 7
        latest = tap.input_events().latest()
        assert latest is not None
        assert latest.event_type == "input.logical.navigation.activate"
        assert latest.source_id == "navigation"
        assert latest.stream_name == "navigation.activate"
        assert latest.stage == "logical"
        assert json.loads(latest.payload_json) == 7

    def test_route_pipeline_instrumentation_preserves_payloads(self) -> None:
        """Verify instrumented Manyfold route streams still emit raw payloads so renderer subscribers never receive TypedEnvelope wrappers."""
        tap = InputDebugTap()
        graph = Graph()
        route_ref = runtime_route("keyboard.snapshot.test", "KeyboardSnapshot")
        source = graph.observe(route_ref, replay_latest=False)
        snapshot = KeyboardSnapshot(
            pressed_keys=frozenset({pygame.K_y}),
            timestamp_ms=123.0,
        )
        observed: list[KeyboardSnapshot] = []

        InputDebugNode(
            tap=tap,
            stage=InputDebugStage.RAW,
            stream_name="keyboard.snapshot",
            source_id="keyboard",
        ).connect(source).subscribe(observed.append)
        graph.publish(route_ref, snapshot)

        history = tap.snapshot()

        assert observed == [snapshot]
        assert history[-1].payload == snapshot

    def test_sparse_tap_emits_without_retaining_history(self) -> None:
        """Keep production input-debug taps cheap unless history is explicitly enabled."""
        tap = InputDebugTap(history_size=0, latency_history_size=0)
        observed = []

        tap.observable().subscribe(observed.append)
        tap.record_latency("frame.tick", 0.001)
        tap.publish(
            stage=InputDebugStage.FRAME,
            stream_name="frame.tick",
            source_id="frame",
            payload=object(),
        )

        assert len(observed) == 1
        assert tap.snapshot() == ()
        assert tap.latency_snapshot() == {}


class TestFrameTickController:
    """Group frame-tick tests so providers can trust one canonical per-frame timing snapshot."""

    def test_advance_emits_frame_snapshot_and_debug_trace(
        self,
        monkeypatch,
    ) -> None:
        """Verify frame ticks emit delta and monotonic timing once per advance so renderer providers can stop joining clock and tick streams."""
        tap = InputDebugTap()
        controller = FrameTickController(tap)
        emitted: list[FrameTick] = []
        monkeypatch.setattr(
            "heart.peripheral.core.input.frame.time.monotonic",
            lambda: 123.456,
        )
        controller.observable().subscribe(emitted.append)

        frame = controller.advance(_StubClock(elapsed_ms=16, fps=60.0))

        assert frame == FrameTick(
            frame_index=0,
            delta_ms=16.0,
            delta_s=0.016,
            monotonic_s=123.456,
            fps=60.0,
        )
        assert emitted == [frame]
        assert tap.snapshot()[-1].stage is InputDebugStage.FRAME
        assert tap.snapshot()[-1].stream_name == "frame.tick"
        assert tap.latency_snapshot()["frame.tick"].count == 1
        latest = controller.topic().latest()
        assert latest is not None
        assert latest.frame_index == 0
        assert latest.delta_ms == 16.0
        assert latest.fps == 60.0


class TestInputStreamHelpers:
    """Cover stream helpers shared across input-derived renderers."""

    def test_average_by_frame_window_emits_once_per_elapsed_window(self) -> None:
        """Verify frame-clocked stream averaging smooths samples without emitting intermediate values."""
        source: NewValues[float | None] = NewValues()
        frame_ticks: NewValues[FrameTick] = NewValues()
        observed: list[float] = []

        average_by_frame_window(
            source.start_with(None),
            frame_ticks,
            interval_ms=100.0,
            selector=lambda value: value,
        ).subscribe(observed.append)

        source.emit(2.0)
        frame_ticks.emit(
            FrameTick(
                frame_index=0,
                delta_ms=40.0,
                delta_s=0.04,
                monotonic_s=1.0,
                fps=25.0,
            )
        )
        source.emit(8.0)
        frame_ticks.emit(
            FrameTick(
                frame_index=1,
                delta_ms=60.0,
                delta_s=0.06,
                monotonic_s=1.06,
                fps=25.0,
            )
        )

        assert observed == [5.0]


class TestKeyboardController:
    """Group keyboard controller tests so shared key views stay stable for every consumer built on them."""

    def test_snapshot_stream_preserves_arrow_key_constants(
        self,
        monkeypatch,
    ) -> None:
        tap = InputDebugTap()
        controller = KeyboardController(tap)
        call_order: list[str] = []
        _enable_keyboard_polling(monkeypatch)

        class _KeyStateStub:
            def __len__(self) -> int:
                return 8

            def __getitem__(self, key: int) -> bool:
                call_order.append("read")
                return key == pygame.K_LEFT

        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.event.pump",
            lambda: call_order.append("pump"),
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.key.get_pressed",
            lambda: _KeyStateStub(),
        )

        snapshots: list[KeyboardSnapshot] = []
        controller.snapshot_stream().subscribe(snapshots.append)
        controller.poll()

        assert snapshots[0].pressed_keys == frozenset({pygame.K_LEFT})
        assert call_order[0] == "pump"
        assert "read" in call_order[1:]

    def test_key_events_emit_pressed_held_and_released_transitions(
        self,
        monkeypatch,
    ) -> None:
        """Verify the controller emits debounced key edges and state views so logical profiles can build on one authoritative keyboard stream."""
        tap = InputDebugTap()
        controller = KeyboardController(tap)
        snapshots: NewValues[KeyboardSnapshot] = NewValues()
        events: list[KeyboardEvent] = []
        states: list[KeyState] = []
        monkeypatch.setattr(controller, "snapshot_stream", lambda: snapshots)

        controller.key_events(pygame.K_a).subscribe(events.append)
        controller.key_state(pygame.K_a).subscribe(states.append)

        snapshots.emit(KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0))
        snapshots.emit(
            KeyboardSnapshot(pressed_keys=frozenset({pygame.K_a}), timestamp_ms=10.0)
        )
        snapshots.emit(
            KeyboardSnapshot(pressed_keys=frozenset({pygame.K_a}), timestamp_ms=20.0)
        )
        snapshots.emit(KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=100.0))

        assert [type(event) for event in events] == [
            KeyPressedEvent,
            KeyHeldEvent,
            KeyReleasedEvent,
        ]
        assert states[0] == KeyState()
        assert states[-1] == KeyState(pressed=False, held=False, last_change_ms=100.0)
        assert any(
            envelope.stream_name == "keyboard.key.a" for envelope in tap.snapshot()
        )
        assert tap.latency_snapshot()["keyboard.key.a"].count == 3


class TestGamepadController:
    """Group gamepad controller tests so button, axis, and stick views remain reusable across renderers and profiles."""

    def test_sample_returns_active_gamepad_without_merging_axes(
        self,
        monkeypatch,
    ) -> None:
        """Verify one active controller wins instead of merging competing slot inputs."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        first = Gamepad(
            joystick_id=0,
            joystick=_JoystickProbe(
                buttons={1: True},
                axes={0: 0.25},
                hat=(1, 0),
            ),
        )
        second = Gamepad(
            joystick_id=1,
            joystick=_JoystickProbe(
                buttons={2: True, 8: True},
                axes={1: -0.75},
                hat=(0, 1),
            ),
        )
        controller = GamepadController(
            manager=_GamepadManager(first, second),
            debug_tap=InputDebugTap(),
        )

        events = controller.sample()

        assert [event.joystick_id for event in events] == [0, 1]
        assert events[0].snapshot.button_held(GamepadButton.SOUTH) is True
        assert events[0].snapshot.button_held(GamepadButton.NORTH) is False
        assert events[0].snapshot.axis_value(GamepadAxis.LEFT_X, dead_zone=0.0) == 0.25
        assert events[0].snapshot.dpad == GamepadDpadValue(x=1)
        assert events[1].snapshot.button_held(GamepadButton.SOUTH) is False
        assert events[1].snapshot.button_held(GamepadButton.NORTH) is True
        assert events[1].snapshot.button_held(GamepadButton.MINUS) is True
        assert events[1].snapshot.axis_value(GamepadAxis.LEFT_Y, dead_zone=0.0) == -0.75
        assert events[1].snapshot.dpad == GamepadDpadValue(y=1)
        latest = controller.input_events().latest()
        assert latest is not None
        assert latest.event_type == "input.raw.gamepad.snapshot"
        assert latest.source_id == "gamepad.1"
        assert latest.stream_name == "gamepad.snapshot"
        payload = json.loads(latest.payload_json)
        assert payload["source"] == "direct.sample"
        assert payload["joystick_id"] == 1
        assert payload["snapshot"]["connected"] is True
        assert payload["snapshot"]["dpad"] == {"x": 0, "y": 1}

    def test_sample_reports_idle_signed_triggers_per_gamepad(
        self,
        monkeypatch,
    ) -> None:
        """Verify trigger rest values stay attached to each physical controller."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        idle = Gamepad(
            joystick_id=0,
            joystick=_JoystickProbe(axes={2: -1.0, 5: -1.0}),
        )
        pressed = Gamepad(
            joystick_id=1,
            joystick=_JoystickProbe(axes={2: 1.0, 5: -1.0}),
        )
        controller = GamepadController(
            manager=_GamepadManager(idle, pressed),
            debug_tap=InputDebugTap(),
        )

        events = controller.sample()

        assert (
            events[0].snapshot.axis_value(GamepadAxis.TRIGGER_LEFT, dead_zone=0.0)
            == -1.0
        )
        assert (
            events[0].snapshot.axis_value(GamepadAxis.TRIGGER_RIGHT, dead_zone=0.0)
            == -1.0
        )
        assert (
            events[1].snapshot.axis_value(GamepadAxis.TRIGGER_LEFT, dead_zone=0.0)
            == 1.0
        )
        assert (
            events[1].snapshot.axis_value(GamepadAxis.TRIGGER_RIGHT, dead_zone=0.0)
            == -1.0
        )

    def test_sample_pumps_pygame_once_for_controller_batch(
        self,
        monkeypatch,
    ) -> None:
        """Verify one all-controller sample pumps SDL once instead of once per joystick."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        now = 1.0
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.time.monotonic",
            lambda: now,
        )
        pump_calls = 0

        def pump() -> None:
            nonlocal pump_calls
            pump_calls += 1

        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.pygame.event.pump",
            pump,
        )
        update_pump_flags: list[bool] = []
        original_update = Gamepad._update

        def update(self: Gamepad, *, pump_events: bool = True) -> None:
            update_pump_flags.append(pump_events)
            original_update(self, pump_events=pump_events)

        monkeypatch.setattr(Gamepad, "_update", update)
        controller = GamepadController(
            manager=_GamepadManager(
                *(
                    Gamepad(
                        joystick_id=joystick_id,
                        joystick=_JoystickProbe(buttons={1: joystick_id == 0}),
                    )
                    for joystick_id in range(4)
                )
            ),
            debug_tap=InputDebugTap(),
        )

        events = controller.sample()
        controller.sample()
        now = 1.008
        controller.sample()

        assert len(events) == 4
        assert pump_calls == 2
        assert update_pump_flags == [False] * 12

    def test_button_taps_emit_on_press_edge(
        self,
        monkeypatch,
    ) -> None:
        """Verify sampled button taps are immediate on press instead of waiting for release."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        joystick = _JoystickProbe(buttons={1: False, 3: False})
        gamepad = Gamepad(joystick_id=0, joystick=joystick)
        controller = GamepadController(
            manager=_GamepadManager(gamepad),
            debug_tap=InputDebugTap(),
        )

        assert controller.sample()[0].snapshot.tapped_buttons == frozenset()

        joystick._buttons[1] = True
        press_snapshot = controller.sample()[0].snapshot
        held_snapshot = controller.sample()[0].snapshot
        joystick._buttons[1] = False
        controller.sample()
        joystick._buttons[3] = True
        y_press_snapshot = controller.sample()[0].snapshot

        assert press_snapshot.tapped_buttons == frozenset({GamepadButton.SOUTH})
        assert held_snapshot.tapped_buttons == frozenset()
        assert y_press_snapshot.tapped_buttons == frozenset({GamepadButton.WEST})

    def test_update_failure_clears_stale_axis_state(self, monkeypatch) -> None:
        """Verify a bad pygame read returns neutral input instead of a stale stick value."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        gamepad = Gamepad(
            joystick_id=0,
            joystick=_JoystickProbe(axes={0: 0.8}),
        )
        controller = GamepadController(
            manager=_GamepadManager(gamepad),
            debug_tap=InputDebugTap(),
        )
        assert (
            controller.sample()[0].snapshot.axis_value(
                GamepadAxis.LEFT_X, dead_zone=0.0
            )
            == 0.8
        )

        gamepad.joystick = _FailingAxisJoystickProbe(axes={0: 0.8})
        snapshot = controller.sample()[0].snapshot

        assert snapshot.axis_value(GamepadAxis.LEFT_X, dead_zone=0.0) == 0.0

    def test_central_poll_retains_controls_for_scenes_and_callbacks(
        self,
        monkeypatch,
    ) -> None:
        input_io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        keyboard = KeyboardSnapshot(
            pressed_keys=frozenset({pygame.K_d}),
            timestamp_ms=10.0,
        )
        gamepad = GamepadSnapshotEvent(
            joystick_id=2,
            snapshot=_gamepad_snapshot(
                axes={
                    GamepadAxis.LEFT_X: 0.75,
                    GamepadAxis.LEFT_Y: -0.25,
                }
            ),
        )
        monkeypatch.setattr(input_io.keyboard, "sample", lambda: keyboard)
        monkeypatch.setattr(
            input_io.gamepad,
            "sample",
            lambda **_kwargs: (gamepad,),
        )
        stick_moves: list[GamepadStickValue] = []
        subscription = input_io.controls.on_stick_move(stick_moves.append)

        polled_keyboard, polled_gamepads = input_io.poll()

        subscription.dispose()
        assert polled_keyboard == keyboard
        assert polled_gamepads == (gamepad,)
        assert input_io.controls.keyboard() == keyboard
        assert input_io.controls.gamepads() == (gamepad,)
        assert stick_moves == [GamepadStickValue(x=0.75, y=-0.25)]


class TestNavigationProfile:
    """Group navigation-profile tests so keyboard and injected inputs produce the shared logical navigation contract."""

    def test_profile_publishes_injected_inputs_as_logical_events(
        self,
        monkeypatch,
    ) -> None:
        """Verify runtime input injections share one PubSub navigation contract."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.io.Configuration.is_debug_mode",
            classmethod(lambda cls: True),
        )
        io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        profile = io.navigation
        intents: list[tuple[str, str, int]] = []
        browse: list[int] = []
        activate: list[str] = []
        alternate: list[str] = []

        profile.intents.subscribe(
            lambda intent: intents.append(
                (
                    type(intent).__name__,
                    intent.source,
                    intent.step if isinstance(intent, BrowseIntent) else 0,
                )
            )
        )
        profile.browse_delta.subscribe(browse.append)
        profile.activate.subscribe(
            lambda intent: activate.append(type(intent).__name__)
        )
        profile.alternate_activate.subscribe(
            lambda intent: alternate.append(type(intent).__name__)
        )

        profile.inject_browse(1, source="gamepad.dpad")
        profile.inject_activate(source="gamepad.south")
        profile.inject_alternate_activate(source="gamepad.north")

        assert browse == [1]
        assert activate == ["ActivateIntent"]
        assert alternate == ["AlternateActivateIntent"]
        assert intents == [
            ("BrowseIntent", "gamepad.dpad", 1),
            ("ActivateIntent", "gamepad.south", 0),
            ("AlternateActivateIntent", "gamepad.north", 0),
        ]

    def test_profile_maps_switch_edges_to_logical_navigation_events(self) -> None:
        """Verify switch rotation and button edges flow into the shared navigation profile so switch-only deployments still browse and activate scenes."""
        switch_updates: NewValues[SwitchState] = NewValues()
        io = InputIO(
            graph=Graph(),
            peripheral_source=lambda: (_SwitchProbe(switch_updates),),
        )
        profile = io.navigation
        intents: list[tuple[str, str, int]] = []

        profile.intents.subscribe(
            lambda intent: intents.append(
                (
                    type(intent).__name__,
                    intent.source,
                    intent.step if isinstance(intent, BrowseIntent) else 0,
                )
            )
        )

        switch_updates.emit(SwitchState(0, 0, 0, 0, 0))
        switch_updates.emit(SwitchState(2, 0, 0, 2, 2))
        switch_updates.emit(SwitchState(2, 1, 0, 0, 2))
        switch_updates.emit(SwitchState(2, 1, 1, 0, 0))

        assert intents == [
            ("BrowseIntent", "switch.rotary", 2),
            ("ActivateIntent", "switch.button", 0),
            ("AlternateActivateIntent", "switch.long_button", 0),
        ]

    def test_profile_tracks_switch_edges_by_source_id(self) -> None:
        """Verify interleaved physical switch updates never compare counters across source IDs."""
        first_updates: NewValues[SwitchState] = NewValues()
        second_updates: NewValues[SwitchState] = NewValues()
        io = InputIO(
            graph=Graph(),
            peripheral_source=lambda: (
                _SwitchProbe(first_updates, source_id="switch:first"),
                _SwitchProbe(second_updates, source_id="switch:second"),
            ),
        )
        profile = io.navigation
        intents: list[tuple[str, str, int]] = []

        profile.intents.subscribe(
            lambda intent: intents.append(
                (
                    type(intent).__name__,
                    intent.source,
                    intent.step if isinstance(intent, BrowseIntent) else 0,
                )
            )
        )

        first_updates.emit(SwitchState(10, 0, 0, 10, 10))
        second_updates.emit(SwitchState(100, 0, 0, 100, 100))
        first_updates.emit(SwitchState(12, 1, 0, 2, 12))
        second_updates.emit(SwitchState(97, 0, 1, -3, 0))

        assert intents == [
            ("BrowseIntent", "switch.rotary", 2),
            ("ActivateIntent", "switch.button", 0),
            ("BrowseIntent", "switch.rotary", -3),
            ("AlternateActivateIntent", "switch.long_button", 0),
        ]


class TestPeripheralInputBus:
    def test_bind_dispatches_mapped_inputs_to_matching_peripherals(
        self, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "heart.peripheral.core.input.io.Configuration.is_debug_mode",
            classmethod(lambda cls: True),
        )
        source: NewValues[int] = NewValues()
        matching = _InputProbe(accepts=True)
        ignored = _InputProbe(accepts=False)
        io = InputIO(
            graph=Graph(),
            peripheral_source=lambda: (matching, ignored),
        )

        subscription = io.peripheral_inputs.bind(
            source,
            lambda value: Input(
                event_type="test.input",
                data={"value": value},
            ),
            target=lambda peripheral: getattr(peripheral, "accepts", False),
        )
        try:
            source.emit(7)
        finally:
            subscription.dispose()

        assert [input_event.data for input_event in matching.inputs] == [{"value": 7}]
        assert ignored.inputs == []
        assert (
            io.debug_tap.snapshot()[-1].stream_name == PERIPHERAL_INPUT_DISPATCH_STREAM
        )


class TestColorInputProfile:
    def test_color_streams_derive_average_rgb_and_hsv_from_final_frame(self) -> None:
        io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        surface = pygame.Surface((2, 2))
        surface.fill((255, 0, 0))
        average_rgb: list[tuple[int, int, int]] = []
        hue: list[float] = []
        saturation: list[float] = []
        brightness: list[float] = []

        subscriptions = [
            io.color.average_rgb().subscribe(average_rgb.append),
            io.color.hue().subscribe(hue.append),
            io.color.saturation().subscribe(saturation.append),
            io.color.brightness().subscribe(brightness.append),
        ]
        try:
            io.final_frame_stream().emit(surface)
        finally:
            for subscription in subscriptions:
                subscription.dispose()

        assert average_rgb == [(255, 0, 0)]
        assert hue == [0.0]
        assert saturation == [1.0]
        assert brightness == [1.0]


class TestMandelbrotControlProfile:
    """Group Mandelbrot profile tests so consumers receive direct motion state and command events instead of decoding merged revisions."""

    def test_profile_splits_motion_state_from_command_events(
        self,
        monkeypatch,
    ) -> None:
        """Verify Mandelbrot consumers can read continuous motion and discrete commands separately so scene controls do not decode unrelated state churn."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        joystick = _JoystickProbe(
            name=GamepadIdentifier.SWITCH_PRO.value,
            axes={0: 0.0, 1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0},
        )
        gamepad = _gamepad_controller_for_joystick(tap, joystick)
        gamepad.poll()
        keyboard_snapshots: NewValues[KeyboardSnapshot] = NewValues()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        motion_states: list[tuple[float, float, bool, bool]] = []
        commands: list[tuple[str, str, str | None, int]] = []

        profile.motion_state.subscribe(
            lambda state: motion_states.append(
                (
                    state.move_x,
                    state.pan_x,
                    state.zoom_in,
                    state.increase_iterations,
                )
            )
        )
        profile.command_events.subscribe(
            lambda command: commands.append(
                (
                    type(command).__name__,
                    command.source,
                    getattr(command, "orientation_kind", None),
                    getattr(command, "palette_delta", 0),
                )
            )
        )

        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_d, timestamp_ms=10.0))
        keyboard_snapshots.emit(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, timestamp_ms=20.0)
        )
        keyboard_snapshots.emit(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, pygame.K_j, timestamp_ms=30.0)
        )
        joystick._axes[2] = 0.5
        gamepad.poll()
        keyboard_snapshots.emit(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_e,
                pygame.K_j,
                pygame.K_i,
                timestamp_ms=40.0,
            )
        )
        keyboard_snapshots.emit(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, pygame.K_j, timestamp_ms=120.0)
        )
        keyboard_snapshots.emit(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_e,
                pygame.K_j,
                pygame.K_0,
                timestamp_ms=130.0,
            )
        )

        assert motion_states[-1] == (1.0, 0.5, True, True)
        assert commands == [
            (ToggleDebugCommand.__name__, "keyboard.i", None, 0),
            (
                SetOrientationCommand.__name__,
                "keyboard.0",
                "rectangle",
                0,
            ),
        ]
        assert any(
            envelope.stream_name == "mandelbrot.motion_state"
            for envelope in tap.snapshot()
        )
        assert any(
            envelope.stream_name == "mandelbrot.command" for envelope in tap.snapshot()
        )

    def test_signed_trigger_axes_drive_zoom(self, monkeypatch) -> None:
        """Verify Mandelbrot triggers work for controllers whose trigger axes rest at -1."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        trigger_right = -1.0

        def latest_gamepad() -> tuple[GamepadSnapshotEvent, ...]:
            return (
                GamepadSnapshotEvent(
                    joystick_id=0,
                    snapshot=_gamepad_snapshot(
                        axes={
                            GamepadAxis.LEFT_X: 0.0,
                            GamepadAxis.LEFT_Y: 0.0,
                            GamepadAxis.RIGHT_X: 0.0,
                            GamepadAxis.RIGHT_Y: 0.0,
                            GamepadAxis.TRIGGER_LEFT: -1.0,
                            GamepadAxis.TRIGGER_RIGHT: trigger_right,
                        },
                    ),
                ),
            )

        monkeypatch.setattr(gamepad, "latest", latest_gamepad)
        keyboard_snapshots: NewValues[KeyboardSnapshot] = NewValues()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        motion_states: list[tuple[bool, bool]] = []

        profile.motion_state.subscribe(
            lambda state: motion_states.append((state.zoom_in, state.zoom_out))
        )

        trigger_right = 1.0
        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=10.0))

        assert motion_states == [(False, False), (True, False)]

    def test_sampled_trigger_axes_do_not_drive_view_mode_buttons(
        self, monkeypatch
    ) -> None:
        """Verify trigger axes stay zoom-only instead of masquerading as bumper commands."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: NewValues())
        monkeypatch.setattr(
            gamepad,
            "snapshot_stream",
            lambda: NewValues(),
            raising=False,
        )
        monkeypatch.setattr(
            gamepad,
            "latest",
            lambda: (
                GamepadSnapshotEvent(
                    joystick_id=0,
                    snapshot=_gamepad_snapshot(
                        axes={
                            GamepadAxis.LEFT_X: 0.0,
                            GamepadAxis.LEFT_Y: 0.0,
                            GamepadAxis.RIGHT_X: 0.0,
                            GamepadAxis.RIGHT_Y: 0.0,
                            GamepadAxis.TRIGGER_LEFT: -1.0,
                            GamepadAxis.TRIGGER_RIGHT: 1.0,
                        },
                    ),
                ),
            ),
        )
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )

        assert profile.sample_gamepad_buttons() == frozenset()

    def test_sampled_bumper_buttons_drive_view_mode_buttons(self, monkeypatch) -> None:
        """Verify physical bumper buttons still resolve to Mandelbrot view-mode commands."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: NewValues())
        monkeypatch.setattr(
            gamepad,
            "snapshot_stream",
            lambda: NewValues(),
            raising=False,
        )
        monkeypatch.setattr(
            gamepad,
            "latest",
            lambda: (
                GamepadSnapshotEvent(
                    joystick_id=0,
                    snapshot=_gamepad_snapshot(
                        buttons={GamepadButton.ZR: True},
                        axes={
                            GamepadAxis.TRIGGER_LEFT: -1.0,
                            GamepadAxis.TRIGGER_RIGHT: -1.0,
                        },
                    ),
                ),
            ),
        )
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )

        assert profile.sample_gamepad_buttons() == frozenset({GamepadButton.ZR})


class TestAccelerometerDebugProfile:
    """Group accelerometer debug-profile tests so keyboard motion debugging stays deterministic across scenes."""

    @pytest.mark.parametrize("external_first", [True, False])
    def test_debug_acceleration_selection_is_callback_order_independent(
        self,
        external_first: bool,
    ) -> None:
        """Prefer active keyboard input and otherwise retain external input."""
        external = NewValues[Acceleration | None]()
        keyboard = NewValues[Acceleration | None]()
        observed: list[Acceleration | None] = []
        subscription = _debug_acceleration_stream(
            cast(
                Subscribable[Acceleration | None],
                PubSubObservable.merge(external),
            ),
            cast(
                Subscribable[Acceleration | None],
                PubSubObservable.merge(keyboard),
            ),
        ).subscribe(observed.append)
        external_initial = Acceleration(x=1.0, y=2.0, z=3.0)
        external_latest = Acceleration(x=4.0, y=5.0, z=6.0)
        keyboard_active = Acceleration(x=7.0, y=8.0, z=9.0)

        try:
            assert external.subscriber_count == 1
            assert keyboard.subscriber_count == 1
            if external_first:
                external.emit(external_initial)
                keyboard.emit(None)
            else:
                keyboard.emit(None)
                external.emit(external_initial)
            keyboard.emit(keyboard_active)
            external.emit(external_latest)
            keyboard.emit(None)
            external.emit(None)

            assert observed == [
                None,
                external_initial,
                keyboard_active,
                external_latest,
                None,
            ]
        finally:
            subscription.dispose()
        assert external.subscriber_count == 0
        assert keyboard.subscriber_count == 0

    def test_controller_node_publishes_physical_acceleration_to_graph(
        self,
        monkeypatch,
    ) -> None:
        """Verify physical accelerometer input is exposed through a graph route handle instead of only a raw stream."""
        accelerometer = FakeAccelerometer()
        source: NewValues[Acceleration | None] = NewValues()
        monkeypatch.setattr(accelerometer, "_event_stream", lambda: source)
        manager = PeripheralManager(
            configuration_loader=cast(Any, _ConfigurationLoaderStub()),
        )
        manager.register(accelerometer)
        graph = manager.graph
        observed: list[Acceleration] = []

        manager.input_io.physical_acceleration().subscribe(observed.append)
        source.emit(Acceleration(x=1.0, y=2.0, z=3.0))

        assert observed == [Acceleration(x=1.0, y=2.0, z=3.0)]
        latest = graph.latest(ACCELERATION_ROUTE)
        assert latest is not None
        assert latest.value == observed[-1]
        assert isinstance(manager.input_io, InputIO)

    def test_profile_emits_keyboard_tilt_and_space_impulse(
        self,
        monkeypatch,
    ) -> None:
        """Verify keyboard tilt and jump keys map to deterministic acceleration vectors so water and Mario scenes share one debug motion contract."""
        tap = InputDebugTap()
        graph = Graph()
        keyboard = KeyboardController(tap)
        frame_ticks = FrameTickController(tap)
        keyboard_snapshots: NewValues[KeyboardSnapshot] = NewValues()
        frame_stream: NewValues[FrameTick] = NewValues()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(frame_ticks, "observable", lambda: frame_stream)
        profile = AccelerometerDebugProfile(
            keyboard_controller=keyboard,
            frame_tick_controller=frame_ticks,
            debug_tap=tap,
            external_sensor_hub=ExternalSensorHub(tap, graph=graph),
            graph=graph,
        )
        observed: list[Acceleration | None] = []
        monkeypatch.setattr(
            "heart.peripheral.core.input.accelerometer.time.monotonic",
            lambda: 10.0,
        )

        profile.observable().subscribe(observed.append)

        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.emit(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_w,
                pygame.K_e,
                pygame.K_SPACE,
                timestamp_ms=10.0,
            )
        )
        frame_stream.emit(
            FrameTick(
                frame_index=0,
                delta_ms=16.0,
                delta_s=0.016,
                monotonic_s=10.05,
                fps=60.0,
            )
        )
        frame_stream.emit(
            FrameTick(
                frame_index=1,
                delta_ms=16.0,
                delta_s=0.016,
                monotonic_s=10.2,
                fps=60.0,
            )
        )

        assert observed[0] == Acceleration(x=1.5, y=1.5, z=13.51)
        assert observed[1] == Acceleration(x=1.5, y=1.5, z=10.51)
        latest = graph.latest(DEBUG_ACCELERATION_ROUTE)
        assert latest is not None
        assert latest.value == observed[-1]
        assert profile.node() is profile.observable()
        assert any(
            envelope.stream_name == "accelerometer.debug" for envelope in tap.snapshot()
        )

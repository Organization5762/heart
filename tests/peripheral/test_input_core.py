"""Validate the graph stream input controller, view, and profile contracts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

import pygame
from manyfold import ConstantNode, Graph, StreamNode

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.input import (AccelerometerDebugProfile,
                                         BrowseIntent, CyclePaletteCommand,
                                         ExternalSensorHub, FrameTick,
                                         FrameTickController, GamepadAxis,
                                         GamepadButton, GamepadButtonTapEvent,
                                         GamepadController, GamepadDpadValue,
                                         GamepadSnapshot, InputDebugStage,
                                         InputDebugTap, InputIO,
                                         KeyboardController, KeyboardSnapshot,
                                         MandelbrotControlProfile,
                                         SetOrientationCommand,
                                         ToggleDebugCommand)
from heart.peripheral.core.input.accelerometer import (
    ACCELERATION_ROUTE, DEBUG_ACCELERATION_ROUTE)
from heart.peripheral.core.input.debug import InputDebugNode
from heart.peripheral.core.input.peripheral_inputs import \
    PERIPHERAL_INPUT_DISPATCH_STREAM
from heart.peripheral.core.input.streams import average_by_frame_window
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.streams import EventStream, runtime_route
from heart.peripheral.gamepad import Gamepad
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
    def __init__(self, stream: EventStream[SwitchState]) -> None:
        super().__init__()
        self._stream = stream

    def _event_stream(self) -> StreamNode[SwitchState]:
        return self._stream.observable()


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


class _GamepadManager:
    def __init__(self, *gamepads: Gamepad) -> None:
        self.peripherals = gamepads


class _InputProbe(Peripheral[int]):
    def __init__(self, *, accepts: bool = True) -> None:
        self.accepts = accepts
        self.inputs: list[Input] = []

    def handle_input(self, input: Input) -> None:
        self.inputs.append(input)


class _ImmediateTimerNode:
    def __init__(
        self,
        value: int = 0,
        transforms: tuple[Callable[[Any], Any], ...] = (),
    ) -> None:
        self._value = value
        self._transforms = transforms

    def then_on_main_thread(self) -> "_ImmediateTimerNode":
        return self

    def map(self, transform: Callable[[Any], Any]) -> "_ImmediateTimerNode":
        return _ImmediateTimerNode(self._value, (*self._transforms, transform))

    def pipe(self, *stream_operators: Callable[[Any], Any]) -> Any:
        stream: Any = self
        for stream_operator in stream_operators:
            stream = stream_operator(stream)
        return stream

    def subscribe(
        self,
        observer: Callable[[Any], None] | Any | None = None,
        on_error: Callable[[Exception], None] | None = None,
        on_completed: Callable[[], None] | None = None,
        scheduler: object | None = None,
        *,
        on_next: Callable[[Any], None] | None = None,
    ) -> _NoopSubscription:
        del on_error, scheduler
        value: Any = self._value
        for transform in self._transforms:
            value = transform(value)
        callback = on_next or observer
        if callable(callback):
            callback(value)
        elif callback is not None:
            callback.on_next(value)
        if on_completed is not None:
            on_completed()
        return _NoopSubscription()


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


class TestInputStreamHelpers:
    """Cover stream helpers shared across input-derived renderers."""

    def test_average_by_frame_window_emits_once_per_elapsed_window(self) -> None:
        """Verify frame-clocked stream averaging smooths samples without emitting intermediate values."""
        source: EventStream[float | None] = EventStream()
        frame_ticks: EventStream[FrameTick] = EventStream()
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

    @staticmethod
    def _immediate_timer(*_args: object, **_kwargs: object) -> object:
        return _ImmediateTimerNode()

    def test_snapshot_stream_preserves_arrow_key_constants(
        self,
        monkeypatch,
    ) -> None:
        """Verify keyboard snapshots preserve arrow-key constants so navigation can detect keys whose pygame codes are outside the base pressed-array index range."""

        tap = InputDebugTap()
        controller = KeyboardController(tap)
        _enable_keyboard_polling(monkeypatch)

        class _KeyStateStub:
            def __len__(self) -> int:
                return 8

            def __getitem__(self, key: int) -> bool:
                return key == pygame.K_LEFT

        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.Timer",
            self._immediate_timer,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.event.pump",
            lambda: None,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.key.get_pressed",
            lambda: _KeyStateStub(),
        )

        snapshots: list[KeyboardSnapshot] = []
        controller.snapshot_stream().subscribe(snapshots.append)

        assert snapshots[0].pressed_keys == frozenset({pygame.K_LEFT})

    def test_snapshot_stream_ignores_arrow_key_index_errors(
        self,
        monkeypatch,
    ) -> None:
        """Verify Linux key-state wrappers that reject SDL2 key constants do not terminate the snapshot stream."""

        tap = InputDebugTap()
        controller = KeyboardController(tap)
        _enable_keyboard_polling(monkeypatch)

        class _KeyStateStub:
            def __len__(self) -> int:
                return 8

            def __getitem__(self, key: int) -> bool:
                if key >= len(self):
                    raise IndexError("list index out of range")
                return False

        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.Timer",
            self._immediate_timer,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.event.pump",
            lambda: None,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.key.get_pressed",
            lambda: _KeyStateStub(),
        )

        snapshots: list[KeyboardSnapshot] = []
        controller.snapshot_stream().subscribe(snapshots.append)

        assert len(snapshots) == 1
        assert snapshots[0].pressed_keys == frozenset()

    def test_snapshot_stream_ignores_indexed_key_state_errors(
        self,
        monkeypatch,
    ) -> None:
        """Verify sparse pygame key-state wrappers cannot terminate keyboard polling during the indexed key scan."""

        tap = InputDebugTap()
        controller = KeyboardController(tap)
        _enable_keyboard_polling(monkeypatch)

        class _KeyStateStub:
            def __len__(self) -> int:
                return 8

            def __getitem__(self, key: int) -> bool:
                if key == 3:
                    raise IndexError("list index out of range")
                return key == 2

        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.Timer",
            self._immediate_timer,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.event.pump",
            lambda: None,
        )
        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.pygame.key.get_pressed",
            lambda: _KeyStateStub(),
        )

        snapshots: list[KeyboardSnapshot] = []
        controller.snapshot_stream().subscribe(snapshots.append)

        assert len(snapshots) == 1
        assert snapshots[0].pressed_keys == frozenset({2})

    def test_snapshot_stream_pumps_pygame_events_before_reading_pressed_keys(
        self,
        monkeypatch,
    ) -> None:
        """Verify keyboard snapshots pump the Pygame event queue before sampling pressed keys so arrow-key navigation sees fresh input state each frame."""

        tap = InputDebugTap()
        controller = KeyboardController(tap)
        call_order: list[str] = []
        _enable_keyboard_polling(monkeypatch)

        class _KeyStateStub:
            def __len__(self) -> int:
                return 8

            def __getitem__(self, key: int) -> bool:
                call_order.append("get_pressed")
                return False

        monkeypatch.setattr(
            "heart.peripheral.core.input.keyboard.Timer",
            self._immediate_timer,
        )
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

        assert len(snapshots) == 1
        assert call_order[0] == "pump"
        assert "get_pressed" in call_order[1:]

    def test_key_events_emit_pressed_held_and_released_transitions(
        self,
        monkeypatch,
    ) -> None:
        """Verify the controller emits debounced key edges and state views so logical profiles can build on one authoritative keyboard stream."""
        tap = InputDebugTap()
        controller = KeyboardController(tap)
        snapshots: EventStream[KeyboardSnapshot] = EventStream()
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

    def test_sample_combines_all_connected_gamepads(
        self,
        monkeypatch,
    ) -> None:
        """Verify primary gamepad input is a centralized snapshot across connected joystick slots."""
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

        snapshot = controller.sample()

        assert snapshot.connected is True
        assert snapshot.identifier == "8BitDo Lite 2+8BitDo Lite 2"
        assert snapshot.button_held(GamepadButton.SOUTH) is True
        assert snapshot.button_held(GamepadButton.NORTH) is True
        assert snapshot.button_held(GamepadButton.MINUS) is True
        assert snapshot.axis_value(GamepadAxis.LEFT_X, dead_zone=0.0) == 0.25
        assert snapshot.axis_value(GamepadAxis.LEFT_Y, dead_zone=0.0) == -0.75
        assert snapshot.dpad == GamepadDpadValue(x=1, y=1)

    def test_sample_can_target_one_gamepad_by_joystick_id(
        self,
        monkeypatch,
    ) -> None:
        """Verify renderers can opt out of the merged primary snapshot and read one physical controller."""
        monkeypatch.setattr(
            "heart.peripheral.core.input.gamepad.Configuration.is_pi",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        first = Gamepad(
            joystick_id=0,
            joystick=_JoystickProbe(buttons={1: True}, hat=(1, 0)),
        )
        second = Gamepad(
            joystick_id=1,
            joystick=_JoystickProbe(buttons={2: True}, hat=(-1, 0)),
        )
        controller = GamepadController(
            manager=_GamepadManager(first, second),
            debug_tap=InputDebugTap(),
        )

        first_snapshot = controller.sample(joystick_id=0)
        second_snapshot = controller.sample(joystick_id=1)

        assert first_snapshot.button_held(GamepadButton.SOUTH) is True
        assert first_snapshot.button_held(GamepadButton.NORTH) is False
        assert first_snapshot.dpad == GamepadDpadValue(x=1)
        assert second_snapshot.button_held(GamepadButton.SOUTH) is False
        assert second_snapshot.button_held(GamepadButton.NORTH) is True
        assert second_snapshot.dpad == GamepadDpadValue(x=-1)

    def test_motion_only_sample_does_not_consume_button_taps(
        self,
        monkeypatch,
    ) -> None:
        """Verify fallback motion reads do not starve one-shot button commands."""
        monkeypatch.setattr(
            "heart.peripheral.gamepad.gamepad.pygame.event.pump", lambda: None
        )
        gamepad = Gamepad(
            joystick_id=0,
            joystick=_JoystickProbe(buttons={1: False}),
        )
        gamepad._tap_flag[1] = True
        controller = GamepadController(
            manager=_GamepadManager(gamepad),
            debug_tap=InputDebugTap(),
        )

        motion_snapshot = controller.sample(include_tapped_buttons=False)
        command_snapshot = controller.sample()

        assert motion_snapshot.tapped_buttons == frozenset()
        assert command_snapshot.tapped_buttons == frozenset({GamepadButton.SOUTH})

    def test_snapshot_stream_can_target_one_gamepad_by_joystick_id(self) -> None:
        """Verify indexed gamepad streams are stable so renderer-specific controller routing can subscribe by slot."""
        controller = GamepadController(
            manager=_GamepadManager(),
            debug_tap=InputDebugTap(),
        )

        indexed_stream = controller.snapshot_stream(joystick_id=1)

        assert indexed_stream is controller.snapshot_stream(joystick_id=1)
        assert indexed_stream is not controller.snapshot_stream()

    def test_views_project_shared_snapshot_state(
        self,
        monkeypatch,
    ) -> None:
        """Verify shared gamepad views derive button taps and stick coordinates from one snapshot stream so consumers stay consistent."""
        tap = InputDebugTap()
        controller = GamepadController(manager=object(), debug_tap=tap)
        snapshots: EventStream[GamepadSnapshot] = EventStream()
        tapped: list[GamepadButtonTapEvent] = []
        sticks: list[tuple[float, float]] = []
        monkeypatch.setattr(controller, "snapshot_stream", lambda: snapshots)

        controller.button_tapped(GamepadButton.SOUTH).subscribe(tapped.append)
        controller.stick_value("left").subscribe(
            lambda stick: sticks.append((stick.x, stick.y))
        )

        snapshots.emit(
            GamepadSnapshot(
                connected=True,
                identifier="pad",
                buttons={GamepadButton.SOUTH: True},
                tapped_buttons=frozenset({GamepadButton.SOUTH}),
                axes={
                    GamepadAxis.LEFT_X: 0.8,
                    GamepadAxis.LEFT_Y: -0.4,
                },
                dpad=GamepadDpadValue(),
                timestamp_monotonic=1.0,
            )
        )

        assert [event.button for event in tapped] == [GamepadButton.SOUTH]
        assert tapped[0].timestamp_monotonic == 1.0
        assert sticks[-1] == (0.8, -0.4)
        assert any(
            envelope.stream_name == "gamepad.stick.left" for envelope in tap.snapshot()
        )


class TestNavigationProfile:
    """Group navigation-profile tests so keyboard and gamepad inputs produce the same logical navigation contract."""

    def test_profile_maps_keyboard_and_gamepad_inputs_to_logical_events(
        self,
        monkeypatch,
    ) -> None:
        """Verify equivalent keyboard and gamepad inputs emit the same navigation outputs so scene navigation remains device-agnostic."""
        io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        tap = io.debug_tap
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(io.keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(io.gamepad, "snapshot_stream", lambda: gamepad_snapshots)
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

        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_LEFT, timestamp_ms=10.0))
        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=100.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_RIGHT, timestamp_ms=110.0))
        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=200.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_DOWN, timestamp_ms=210.0))
        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=300.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_UP, timestamp_ms=310.0))

        gamepad_snapshots.emit(_gamepad_snapshot(timestamp_monotonic=1.0))
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                dpad=GamepadDpadValue(x=1),
                timestamp_monotonic=2.0,
            )
        )
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                tapped_buttons=frozenset({GamepadButton.SOUTH}),
                dpad=GamepadDpadValue(x=1),
                timestamp_monotonic=3.0,
            )
        )
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                tapped_buttons=frozenset({GamepadButton.NORTH}),
                dpad=GamepadDpadValue(x=1),
                timestamp_monotonic=4.0,
            )
        )

        assert browse == [-1, 1, 1]
        assert activate == ["ActivateIntent", "ActivateIntent"]
        assert alternate == [
            "AlternateActivateIntent",
            "AlternateActivateIntent",
        ]
        assert intents == [
            ("BrowseIntent", "keyboard.left", -1),
            ("BrowseIntent", "keyboard.right", 1),
            ("ActivateIntent", "keyboard.down", 0),
            ("AlternateActivateIntent", "keyboard.up", 0),
            ("BrowseIntent", "gamepad.dpad", 1),
            ("ActivateIntent", "gamepad.south", 0),
            ("AlternateActivateIntent", "gamepad.north", 0),
        ]
        assert any(
            envelope.stream_name == "navigation.intent" for envelope in tap.snapshot()
        )

    def test_profile_maps_switch_edges_to_logical_navigation_events(self) -> None:
        """Verify switch rotation and button edges flow into the shared navigation profile so switch-only deployments still browse and activate scenes."""
        switch_updates: EventStream[SwitchState] = EventStream()
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

    def test_subscribe_events_binds_requested_navigation_handlers(self) -> None:
        """Verify subscribe_events wires the requested logical handlers in one place so navigation consumers do not duplicate subscription setup."""
        switch_updates: EventStream[SwitchState] = EventStream()
        io = InputIO(
            graph=Graph(),
            peripheral_source=lambda: (_SwitchProbe(switch_updates),),
        )
        profile = io.navigation
        browse: list[int] = []
        activate: list[str] = []
        alternate: list[str] = []

        subscription = profile.subscribe_events(
            on_browse_delta=browse.append,
            on_activate=lambda _intent: activate.append("activate"),
            on_alternate_activate=lambda _intent: alternate.append("alternate"),
        )

        switch_updates.emit(SwitchState(0, 0, 0, 0, 0))
        switch_updates.emit(SwitchState(3, 0, 0, 3, 3))
        switch_updates.emit(SwitchState(3, 1, 0, 0, 3))
        switch_updates.emit(SwitchState(3, 1, 1, 0, 0))

        subscription.dispose()

        assert browse == [3]
        assert activate == ["activate"]
        assert alternate == ["alternate"]


class TestPeripheralInputBus:
    def test_bind_dispatches_mapped_inputs_to_matching_peripherals(self) -> None:
        source: EventStream[int] = EventStream()
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

    def test_bind_without_targets_does_not_subscribe_to_source(self) -> None:
        source: EventStream[int] = EventStream()
        io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        calls: list[int] = []

        subscription = io.peripheral_inputs.bind(
            source.map(lambda value: calls.append(value) or value),
            lambda value: Input(event_type="test.input", data=value),
        )
        try:
            source.emit(1)
        finally:
            subscription.dispose()

        assert calls == []


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

    def test_color_snapshot_is_not_computed_without_subscribers(
        self,
        monkeypatch,
    ) -> None:
        io = InputIO(graph=Graph(), peripheral_source=lambda: ())
        surface = pygame.Surface((1, 1))
        calls: list[pygame.Surface] = []

        def average_color(candidate: pygame.Surface) -> tuple[int, int, int, int]:
            calls.append(candidate)
            return (0, 0, 0, 255)

        monkeypatch.setattr(pygame.transform, "average_color", average_color)

        io.final_frame_stream().emit(surface)

        assert calls == []


class TestMandelbrotControlProfile:
    """Group Mandelbrot profile tests so consumers receive direct motion state and command events instead of decoding merged revisions."""

    def test_profile_splits_motion_state_from_command_events(
        self,
        monkeypatch,
    ) -> None:
        """Verify Mandelbrot consumers can read continuous motion and discrete commands separately so scene controls do not decode unrelated state churn."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(gamepad, "snapshot_stream", lambda: gamepad_snapshots)
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

        gamepad_snapshots.emit(_gamepad_snapshot(timestamp_monotonic=1.0))
        keyboard_snapshots.emit(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.emit(_keyboard_snapshot(pygame.K_d, timestamp_ms=10.0))
        keyboard_snapshots.emit(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, timestamp_ms=20.0)
        )
        keyboard_snapshots.emit(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, pygame.K_j, timestamp_ms=30.0)
        )
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                dpad=GamepadDpadValue(x=-1, y=1),
                axes={
                    GamepadAxis.LEFT_X: 0.0,
                    GamepadAxis.LEFT_Y: 0.0,
                    GamepadAxis.RIGHT_X: 0.5,
                    GamepadAxis.RIGHT_Y: 0.0,
                    GamepadAxis.TRIGGER_LEFT: 0.0,
                    GamepadAxis.TRIGGER_RIGHT: 0.0,
                },
                timestamp_monotonic=2.0,
            )
        )
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
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                tapped_buttons=frozenset({GamepadButton.NORTH}),
                axes={
                    GamepadAxis.LEFT_X: 0.0,
                    GamepadAxis.LEFT_Y: 0.0,
                    GamepadAxis.RIGHT_X: 0.5,
                    GamepadAxis.RIGHT_Y: 0.0,
                    GamepadAxis.TRIGGER_LEFT: 0.0,
                    GamepadAxis.TRIGGER_RIGHT: 0.0,
                },
                timestamp_monotonic=3.0,
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
            (CyclePaletteCommand.__name__, "gamepad.north", None, 1),
        ]
        assert any(
            envelope.stream_name == "mandelbrot.motion_state"
            for envelope in tap.snapshot()
        )
        assert any(
            envelope.stream_name == "mandelbrot.command" for envelope in tap.snapshot()
        )

    def test_motion_state_uses_gamepad_snapshot_without_keyboard_tick(
        self,
        monkeypatch,
    ) -> None:
        """Verify gamepad movement is not blocked waiting for derived keyboard/gamepad view streams."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(gamepad, "snapshot_stream", lambda: gamepad_snapshots)
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        motion_states: list[tuple[float, float, float, float]] = []

        profile.motion_state.subscribe(
            lambda state: motion_states.append(
                (state.move_x, state.move_y, state.pan_x, state.pan_y)
            )
        )

        gamepad_snapshots.emit(
            _gamepad_snapshot(
                dpad=GamepadDpadValue(x=1, y=-1),
                axes={
                    GamepadAxis.LEFT_X: 0.5,
                    GamepadAxis.LEFT_Y: -0.25,
                    GamepadAxis.RIGHT_X: 0.6,
                    GamepadAxis.RIGHT_Y: -0.7,
                    GamepadAxis.TRIGGER_LEFT: 0.0,
                    GamepadAxis.TRIGGER_RIGHT: 0.0,
                },
                timestamp_monotonic=2.0,
            )
        )

        assert motion_states[-1] == (1.5, 0.75, 0.6, 0.7)

    def test_left_stick_y_matches_keyboard_movement_direction(
        self,
        monkeypatch,
    ) -> None:
        """Keep Mandelbrot left-stick vertical motion aligned with W/S movement."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(gamepad, "snapshot_stream", lambda: gamepad_snapshots)
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        motion_states: list[tuple[float, float]] = []

        profile.motion_state.subscribe(
            lambda state: motion_states.append((state.move_x, state.move_y))
        )

        gamepad_snapshots.emit(
            _gamepad_snapshot(
                axes={
                    GamepadAxis.LEFT_X: 0.0,
                    GamepadAxis.LEFT_Y: -0.5,
                    GamepadAxis.RIGHT_X: 0.0,
                    GamepadAxis.RIGHT_Y: 0.0,
                    GamepadAxis.TRIGGER_LEFT: 0.0,
                    GamepadAxis.TRIGGER_RIGHT: 0.0,
                },
                timestamp_monotonic=2.0,
            )
        )

        assert motion_states[-1] == (0.0, -0.5)

    def test_signed_trigger_axes_drive_zoom(self, monkeypatch) -> None:
        """Verify Mandelbrot triggers work for controllers whose trigger axes rest at -1."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        gamepad_snapshots: EventStream[GamepadSnapshot] = EventStream()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(gamepad, "snapshot_stream", lambda: gamepad_snapshots)
        profile = MandelbrotControlProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        motion_states: list[tuple[bool, bool]] = []

        profile.motion_state.subscribe(
            lambda state: motion_states.append((state.zoom_in, state.zoom_out))
        )

        gamepad_snapshots.emit(
            _gamepad_snapshot(
                axes={
                    GamepadAxis.LEFT_X: 0.0,
                    GamepadAxis.LEFT_Y: 0.0,
                    GamepadAxis.RIGHT_X: 0.0,
                    GamepadAxis.RIGHT_Y: 0.0,
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                    GamepadAxis.TRIGGER_RIGHT: -1.0,
                },
                timestamp_monotonic=2.0,
            )
        )
        gamepad_snapshots.emit(
            _gamepad_snapshot(
                axes={
                    GamepadAxis.LEFT_X: 0.0,
                    GamepadAxis.LEFT_Y: 0.0,
                    GamepadAxis.RIGHT_X: 0.0,
                    GamepadAxis.RIGHT_Y: 0.0,
                    GamepadAxis.TRIGGER_LEFT: -1.0,
                    GamepadAxis.TRIGGER_RIGHT: 1.0,
                },
                timestamp_monotonic=3.0,
            )
        )

        assert motion_states == [(False, False), (True, False)]


class TestAccelerometerDebugProfile:
    """Group accelerometer debug-profile tests so keyboard motion debugging stays deterministic across scenes."""

    def test_controller_node_publishes_physical_acceleration_to_graph(
        self,
        monkeypatch,
    ) -> None:
        """Verify physical accelerometer input is exposed through a graph route handle instead of only a raw stream."""
        accelerometer = FakeAccelerometer()
        source: EventStream[Acceleration | None] = EventStream()
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
        keyboard_snapshots: EventStream[KeyboardSnapshot] = EventStream()
        frame_stream: EventStream[FrameTick] = EventStream()
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

        assert observed[0] is None
        assert observed[1] == Acceleration(x=1.5, y=1.5, z=13.51)
        assert observed[2] == Acceleration(x=1.5, y=1.5, z=10.51)
        latest = graph.latest(DEBUG_ACCELERATION_ROUTE)
        assert latest is not None
        assert latest.value == observed[-1]
        assert profile.node() is profile.observable()
        assert any(
            envelope.stream_name == "accelerometer.debug" for envelope in tap.snapshot()
        )

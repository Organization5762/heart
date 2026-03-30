"""Validate the new Rx-first input controller, view, and profile contracts."""

from __future__ import annotations

import pygame
import reactivex
from reactivex.subject import BehaviorSubject, Subject

from heart.peripheral.core.input import (AccelerometerDebugProfile, FrameTick,
                                         FrameTickController, GamepadAxis,
                                         GamepadButton, GamepadController,
                                         GamepadDpadValue, GamepadSnapshot,
                                         InputDebugStage, InputDebugTap,
                                         KeyboardController, KeyboardSnapshot,
                                         NavigationProfile)
from heart.peripheral.core.input.debug import instrument_input_stream
from heart.peripheral.keyboard import KeyboardAction, KeyboardEvent, KeyState
from heart.peripheral.sensor import Acceleration


class _StubClock:
    def __init__(self, elapsed_ms: int, fps: float) -> None:
        self._elapsed_ms = elapsed_ms
        self._fps = fps

    def get_time(self) -> int:
        return self._elapsed_ms

    def get_fps(self) -> float:
        return self._fps


class _StubKeyboardController:
    def __init__(self) -> None:
        self._pressed: dict[int, Subject[KeyboardEvent]] = {}
        self._states: dict[int, BehaviorSubject[KeyState]] = {}

    def key_pressed(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        return self._pressed.setdefault(key, Subject())

    def key_state(self, key: int) -> reactivex.Observable[KeyState]:
        return self._states.setdefault(key, BehaviorSubject(KeyState()))

    def emit_pressed(self, key: int) -> None:
        event = KeyboardEvent(
            key=key,
            key_name=pygame.key.name(key),
            action=KeyboardAction.PRESSED,
            state=KeyState(pressed=True, held=False, last_change_ms=1.0),
            timestamp_ms=1.0,
        )
        self._pressed.setdefault(key, Subject()).on_next(event)

    def emit_state(self, key: int, *, pressed: bool, held: bool = False) -> None:
        self._states.setdefault(key, BehaviorSubject(KeyState())).on_next(
            KeyState(pressed=pressed, held=held, last_change_ms=1.0)
        )


class _StubGamepadController:
    def __init__(self) -> None:
        self._button_tapped: dict[GamepadButton, Subject[GamepadButton]] = {}
        self._axis_values: dict[tuple[GamepadAxis, float], BehaviorSubject[float]] = {}
        self._dpad = BehaviorSubject(GamepadDpadValue())

    def button_tapped(self, button: GamepadButton) -> reactivex.Observable[GamepadButton]:
        return self._button_tapped.setdefault(button, Subject())

    def dpad_value(self) -> reactivex.Observable[GamepadDpadValue]:
        return self._dpad

    def axis_value(
        self,
        axis: GamepadAxis,
        dead_zone: float = 0.1,
    ) -> reactivex.Observable[float]:
        return self._axis_values.setdefault((axis, dead_zone), BehaviorSubject(0.0))

    def emit_button_tapped(self, button: GamepadButton) -> None:
        self._button_tapped.setdefault(button, Subject()).on_next(button)

    def emit_dpad(self, *, x: int, y: int = 0) -> None:
        self._dpad.on_next(GamepadDpadValue(x=x, y=y))

    def emit_axis(
        self,
        axis: GamepadAxis,
        value: float,
        *,
        dead_zone: float = 0.1,
    ) -> None:
        self._axis_values.setdefault((axis, dead_zone), BehaviorSubject(0.0)).on_next(
            value
        )


class _StubFrameTickController:
    def __init__(self) -> None:
        self._subject: Subject[FrameTick] = Subject()

    def observable(self) -> reactivex.Observable[FrameTick]:
        return self._subject

    def emit(self, frame_tick: FrameTick) -> None:
        self._subject.on_next(frame_tick)


class TestInputDebugTap:
    """Group debug-tap tests so traced input lineage stays inspectable during runtime and tests."""

    def test_instrumented_stream_records_stage_and_lineage(self) -> None:
        """Verify instrumented streams publish trace envelopes so developers can follow input emissions across layers."""
        tap = InputDebugTap()
        observed: list[int] = []

        instrument_input_stream(
            reactivex.from_iterable([7]),
            tap=tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.activate",
            source_id="navigation",
            upstream_ids=("keyboard.pressed.down",),
        ).subscribe(observed.append)

        history = tap.snapshot()

        assert observed == [7]
        assert len(history) == 1
        assert history[0].stage is InputDebugStage.LOGICAL
        assert history[0].stream_name == "navigation.activate"
        assert history[0].source_id == "navigation"
        assert history[0].upstream_ids == ("keyboard.pressed.down",)
        assert history[0].payload == 7


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


class TestKeyboardController:
    """Group keyboard controller tests so shared key views stay stable for every consumer built on them."""

    def test_key_events_emit_pressed_held_and_released_transitions(
        self,
        monkeypatch,
    ) -> None:
        """Verify the controller emits debounced key edges and state views so logical profiles can build on one authoritative keyboard stream."""
        tap = InputDebugTap()
        controller = KeyboardController(tap)
        snapshots: Subject[KeyboardSnapshot] = Subject()
        events: list[KeyboardEvent] = []
        states: list[KeyState] = []
        monkeypatch.setattr(controller, "snapshot_stream", lambda: snapshots)

        controller.key_events(pygame.K_a).subscribe(events.append)
        controller.key_state(pygame.K_a).subscribe(states.append)

        snapshots.on_next(KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0))
        snapshots.on_next(
            KeyboardSnapshot(pressed_keys=frozenset({pygame.K_a}), timestamp_ms=10.0)
        )
        snapshots.on_next(
            KeyboardSnapshot(pressed_keys=frozenset({pygame.K_a}), timestamp_ms=20.0)
        )
        snapshots.on_next(KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=100.0))

        assert [event.action for event in events] == [
            KeyboardAction.PRESSED,
            KeyboardAction.HELD,
            KeyboardAction.RELEASED,
        ]
        assert states[0] == KeyState()
        assert states[-1] == KeyState(pressed=False, held=False, last_change_ms=100.0)
        assert any(
            envelope.stream_name == "keyboard.key.a"
            for envelope in tap.snapshot()
        )
        assert tap.latency_snapshot()["keyboard.key.a"].count == 3


class TestGamepadController:
    """Group gamepad controller tests so button, axis, and stick views remain reusable across renderers and profiles."""

    def test_views_project_shared_snapshot_state(
        self,
        monkeypatch,
    ) -> None:
        """Verify shared gamepad views derive button taps and stick coordinates from one snapshot stream so consumers stay consistent."""
        tap = InputDebugTap()
        controller = GamepadController(manager=object(), debug_tap=tap)
        snapshots: Subject[GamepadSnapshot] = Subject()
        tapped: list[GamepadButton] = []
        sticks: list[tuple[float, float]] = []
        monkeypatch.setattr(controller, "snapshot_stream", lambda: snapshots)

        controller.button_tapped(GamepadButton.SOUTH).subscribe(tapped.append)
        controller.stick_value("left").subscribe(
            lambda stick: sticks.append((stick.x, stick.y))
        )

        snapshots.on_next(
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

        assert tapped == [GamepadButton.SOUTH]
        assert sticks[-1] == (0.8, -0.4)
        assert any(
            envelope.stream_name == "gamepad.stick.left"
            for envelope in tap.snapshot()
        )


class TestNavigationProfile:
    """Group navigation-profile tests so keyboard and gamepad inputs produce the same logical navigation contract."""

    def test_profile_maps_keyboard_and_gamepad_inputs_to_logical_events(self) -> None:
        """Verify equivalent keyboard and gamepad inputs emit the same navigation outputs so scene navigation remains device-agnostic."""
        keyboard = _StubKeyboardController()
        gamepad = _StubGamepadController()
        tap = InputDebugTap()
        profile = NavigationProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
        browse: list[int] = []
        activate: list[str] = []
        alternate: list[str] = []

        profile.browse_delta.subscribe(browse.append)
        profile.activate.subscribe(activate.append)
        profile.alternate_activate.subscribe(alternate.append)

        keyboard.emit_pressed(pygame.K_LEFT)
        keyboard.emit_pressed(pygame.K_RIGHT)
        keyboard.emit_pressed(pygame.K_DOWN)
        keyboard.emit_pressed(pygame.K_UP)
        gamepad.emit_dpad(x=1)
        gamepad.emit_button_tapped(GamepadButton.SOUTH)
        gamepad.emit_button_tapped(GamepadButton.NORTH)

        assert browse == [-1, 1, 1]
        assert activate == ["activate", "activate"]
        assert alternate == ["alternate_activate", "alternate_activate"]
        assert any(
            envelope.stream_name == "navigation.browse_delta"
            for envelope in tap.snapshot()
        )


class TestAccelerometerDebugProfile:
    """Group accelerometer debug-profile tests so keyboard motion debugging stays deterministic across scenes."""

    def test_profile_emits_keyboard_tilt_and_space_impulse(
        self,
        monkeypatch,
    ) -> None:
        """Verify keyboard tilt and jump keys map to deterministic acceleration vectors so water and Mario scenes share one debug motion contract."""
        keyboard = _StubKeyboardController()
        frame_ticks = _StubFrameTickController()
        tap = InputDebugTap()
        profile = AccelerometerDebugProfile(
            keyboard_controller=keyboard,
            frame_tick_controller=frame_ticks,
            debug_tap=tap,
        )
        observed: list[Acceleration] = []
        monkeypatch.setattr(
            "heart.peripheral.core.input.accelerometer.time.monotonic",
            lambda: 10.0,
        )

        profile.observable().subscribe(observed.append)

        keyboard.emit_state(pygame.K_d, pressed=True)
        keyboard.emit_state(pygame.K_w, pressed=True)
        keyboard.emit_state(pygame.K_e, pressed=True)
        keyboard.emit_pressed(pygame.K_SPACE)
        frame_ticks.emit(
            FrameTick(
                frame_index=0,
                delta_ms=16.0,
                delta_s=0.016,
                monotonic_s=10.05,
                fps=60.0,
            )
        )
        frame_ticks.emit(
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
        assert any(
            envelope.stream_name == "accelerometer.debug"
            for envelope in tap.snapshot()
        )

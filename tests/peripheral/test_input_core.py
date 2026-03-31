"""Validate the new Rx-first input controller, view, and profile contracts."""

from __future__ import annotations

import pygame
import reactivex
from reactivex.subject import Subject

from heart.peripheral.core.input import (AccelerometerDebugProfile,
                                         BrowseIntent, CyclePaletteCommand,
                                         FrameTick, FrameTickController,
                                         GamepadAxis, GamepadButton,
                                         GamepadButtonTapEvent,
                                         GamepadController, GamepadDpadValue,
                                         GamepadSnapshot, InputDebugStage,
                                         InputDebugTap, KeyboardController,
                                         KeyboardSnapshot,
                                         MandelbrotControlProfile,
                                         NavigationProfile,
                                         SetOrientationCommand,
                                         ToggleDebugCommand)
from heart.peripheral.core.input.debug import instrument_input_stream
from heart.peripheral.keyboard import (KeyboardEvent, KeyHeldEvent,
                                       KeyPressedEvent, KeyReleasedEvent,
                                       KeyState)
from heart.peripheral.sensor import Acceleration
from heart.peripheral.switch import SwitchState


class _StubClock:
    def __init__(self, elapsed_ms: int, fps: float) -> None:
        self._elapsed_ms = elapsed_ms
        self._fps = fps

    def get_time(self) -> int:
        return self._elapsed_ms

    def get_fps(self) -> float:
        return self._fps


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

        assert [type(event) for event in events] == [
            KeyPressedEvent,
            KeyHeldEvent,
            KeyReleasedEvent,
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
        tapped: list[GamepadButtonTapEvent] = []
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

        assert [event.button for event in tapped] == [GamepadButton.SOUTH]
        assert tapped[0].timestamp_monotonic == 1.0
        assert sticks[-1] == (0.8, -0.4)
        assert any(
            envelope.stream_name == "gamepad.stick.left"
            for envelope in tap.snapshot()
        )


class TestNavigationProfile:
    """Group navigation-profile tests so keyboard and gamepad inputs produce the same logical navigation contract."""

    def test_profile_maps_keyboard_and_gamepad_inputs_to_logical_events(
        self,
        monkeypatch,
    ) -> None:
        """Verify equivalent keyboard and gamepad inputs emit the same navigation outputs so scene navigation remains device-agnostic."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        keyboard_snapshots: Subject[KeyboardSnapshot] = Subject()
        gamepad_snapshots: Subject[GamepadSnapshot] = Subject()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(gamepad, "snapshot_stream", lambda: gamepad_snapshots)
        profile = NavigationProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
        )
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
        profile.activate.subscribe(lambda intent: activate.append(type(intent).__name__))
        profile.alternate_activate.subscribe(
            lambda intent: alternate.append(type(intent).__name__)
        )

        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(pygame.K_LEFT, timestamp_ms=10.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=100.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(pygame.K_RIGHT, timestamp_ms=110.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=200.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(pygame.K_DOWN, timestamp_ms=210.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=300.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(pygame.K_UP, timestamp_ms=310.0))

        gamepad_snapshots.on_next(_gamepad_snapshot(timestamp_monotonic=1.0))
        gamepad_snapshots.on_next(
            _gamepad_snapshot(
                dpad=GamepadDpadValue(x=1),
                timestamp_monotonic=2.0,
            )
        )
        gamepad_snapshots.on_next(
            _gamepad_snapshot(
                tapped_buttons=frozenset({GamepadButton.SOUTH}),
                dpad=GamepadDpadValue(x=1),
                timestamp_monotonic=3.0,
            )
        )
        gamepad_snapshots.on_next(
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
            envelope.stream_name == "navigation.intent"
            for envelope in tap.snapshot()
        )

    def test_profile_maps_switch_edges_to_logical_navigation_events(self) -> None:
        """Verify switch rotation and button edges flow into the shared navigation profile so switch-only deployments still browse and activate scenes."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        switch_updates: Subject[SwitchState] = Subject()
        profile = NavigationProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
            switch_stream_factory=lambda: switch_updates,
        )
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

        switch_updates.on_next(SwitchState(0, 0, 0, 0, 0))
        switch_updates.on_next(SwitchState(2, 0, 0, 2, 2))
        switch_updates.on_next(SwitchState(2, 1, 0, 0, 2))
        switch_updates.on_next(SwitchState(2, 1, 1, 0, 0))

        assert intents == [
            ("BrowseIntent", "switch.rotary", 2),
            ("ActivateIntent", "switch.button", 0),
            ("AlternateActivateIntent", "switch.long_button", 0),
        ]

    def test_subscribe_events_binds_requested_navigation_handlers(self) -> None:
        """Verify subscribe_events wires the requested logical handlers in one place so navigation consumers do not duplicate reactive subscription setup."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        gamepad = GamepadController(manager=object(), debug_tap=tap)
        switch_updates: Subject[SwitchState] = Subject()
        profile = NavigationProfile(
            keyboard_controller=keyboard,
            gamepad_controller=gamepad,
            debug_tap=tap,
            switch_stream_factory=lambda: switch_updates,
        )
        browse: list[int] = []
        activate: list[str] = []
        alternate: list[str] = []

        subscription = profile.subscribe_events(
            on_browse_delta=browse.append,
            on_activate=lambda _intent: activate.append("activate"),
            on_alternate_activate=lambda _intent: alternate.append("alternate"),
        )

        switch_updates.on_next(SwitchState(0, 0, 0, 0, 0))
        switch_updates.on_next(SwitchState(3, 0, 0, 3, 3))
        switch_updates.on_next(SwitchState(3, 1, 0, 0, 3))
        switch_updates.on_next(SwitchState(3, 1, 1, 0, 0))

        subscription.dispose()

        assert browse == [3]
        assert activate == ["activate"]
        assert alternate == ["alternate"]


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
        keyboard_snapshots: Subject[KeyboardSnapshot] = Subject()
        gamepad_snapshots: Subject[GamepadSnapshot] = Subject()
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

        gamepad_snapshots.on_next(_gamepad_snapshot(timestamp_monotonic=1.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.on_next(_keyboard_snapshot(pygame.K_d, timestamp_ms=10.0))
        keyboard_snapshots.on_next(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, timestamp_ms=20.0)
        )
        keyboard_snapshots.on_next(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, pygame.K_j, timestamp_ms=30.0)
        )
        gamepad_snapshots.on_next(
            _gamepad_snapshot(
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
        keyboard_snapshots.on_next(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_e,
                pygame.K_j,
                pygame.K_i,
                timestamp_ms=40.0,
            )
        )
        keyboard_snapshots.on_next(
            _keyboard_snapshot(pygame.K_d, pygame.K_e, pygame.K_j, timestamp_ms=120.0)
        )
        keyboard_snapshots.on_next(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_e,
                pygame.K_j,
                pygame.K_0,
                timestamp_ms=130.0,
            )
        )
        gamepad_snapshots.on_next(
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
            envelope.stream_name == "mandelbrot.command"
            for envelope in tap.snapshot()
        )


class TestAccelerometerDebugProfile:
    """Group accelerometer debug-profile tests so keyboard motion debugging stays deterministic across scenes."""

    def test_profile_emits_keyboard_tilt_and_space_impulse(
        self,
        monkeypatch,
    ) -> None:
        """Verify keyboard tilt and jump keys map to deterministic acceleration vectors so water and Mario scenes share one debug motion contract."""
        tap = InputDebugTap()
        keyboard = KeyboardController(tap)
        frame_ticks = FrameTickController(tap)
        keyboard_snapshots: Subject[KeyboardSnapshot] = Subject()
        frame_stream: Subject[FrameTick] = Subject()
        monkeypatch.setattr(keyboard, "snapshot_stream", lambda: keyboard_snapshots)
        monkeypatch.setattr(frame_ticks, "observable", lambda: frame_stream)
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

        keyboard_snapshots.on_next(_keyboard_snapshot(timestamp_ms=0.0))
        keyboard_snapshots.on_next(
            _keyboard_snapshot(
                pygame.K_d,
                pygame.K_w,
                pygame.K_e,
                pygame.K_SPACE,
                timestamp_ms=10.0,
            )
        )
        frame_stream.on_next(
            FrameTick(
                frame_index=0,
                delta_ms=16.0,
                delta_s=0.016,
                monotonic_s=10.05,
                fps=60.0,
            )
        )
        frame_stream.on_next(
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

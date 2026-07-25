from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import pygame

from heart.peripheral.core.input.debug import InputDebugTap
from heart.peripheral.core.input.events import (GamepadInputState, InputEvent,
                                                gamepad_state_topic,
                                                input_event_topic)
from heart.peripheral.gamepad import Gamepad, GamepadIdentifier
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth,
                                                          DpadType,
                                                          SwitchLikeMapping,
                                                          SwitchProMapping)
from heart.peripheral.gamepad.screen_mapping import screen_slot_for_joystick
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from heart.peripheral.core.manager import PeripheralManager
DEFAULT_GAMEPAD_AXIS_DEAD_ZONE = 0.1
GAMEPAD_PUMP_THROTTLE_SECONDS = 0.007
GAMEPAD_STATS_LOG_INTERVAL_SECONDS = 5.0


class GamepadButton(StrEnum):
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    PLUS = "plus"
    MINUS = "minus"
    HOME = "home"
    CAPTURE = "capture"
    ZL = "zl"
    ZR = "zr"
    L3 = "l3"
    R3 = "r3"


class GamepadAxis(StrEnum):
    LEFT_X = "left_x"
    LEFT_Y = "left_y"
    RIGHT_X = "right_x"
    RIGHT_Y = "right_y"
    TRIGGER_LEFT = "trigger_left"
    TRIGGER_RIGHT = "trigger_right"


ButtonId = Callable[[SwitchLikeMapping], int]

GAMEPAD_BUTTON_MAPPING_ACCESSORS: tuple[tuple[GamepadButton, ButtonId], ...] = (
    (GamepadButton.SOUTH, lambda mapping: mapping.BUTTON_B),
    (GamepadButton.EAST, lambda mapping: mapping.BUTTON_A),
    (GamepadButton.WEST, lambda mapping: mapping.BUTTON_Y),
    (GamepadButton.NORTH, lambda mapping: mapping.BUTTON_X),
    (GamepadButton.PLUS, lambda mapping: mapping.BUTTON_PLUS),
    (GamepadButton.MINUS, lambda mapping: mapping.BUTTON_MINUS),
    (GamepadButton.HOME, lambda mapping: mapping.BUTTON_HOME),
    (GamepadButton.CAPTURE, lambda mapping: mapping.BUTTON_CAPTURE),
    (GamepadButton.ZL, lambda mapping: mapping.BUTTON_ZL),
    (GamepadButton.ZR, lambda mapping: mapping.BUTTON_ZR),
    (GamepadButton.L3, lambda mapping: mapping.BUTTON_L3),
    (GamepadButton.R3, lambda mapping: mapping.BUTTON_R3),
)


@dataclass(frozen=True, slots=True)
class GamepadStickValue:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class GamepadDpadValue:
    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True)
class GamepadButtonTapEvent:
    button: GamepadButton
    timestamp_monotonic: float


@dataclass(frozen=True, slots=True)
class GamepadSnapshotEvent:
    joystick_id: int
    snapshot: "GamepadSnapshot"


@dataclass(frozen=True, slots=True)
class GamepadSnapshot:
    connected: bool
    identifier: str | None
    buttons: dict[GamepadButton, bool] = field(default_factory=dict)
    tapped_buttons: frozenset[GamepadButton] = frozenset()
    axes: dict[GamepadAxis, float] = field(default_factory=dict)
    dpad: GamepadDpadValue = GamepadDpadValue()
    timestamp_monotonic: float = 0.0

    def button_held(self, button: GamepadButton) -> bool:
        return self.buttons.get(button, False)

    def button_tapped(self, button: GamepadButton) -> bool:
        return button in self.tapped_buttons

    def axis_value(
        self, axis: GamepadAxis, *, dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
    ) -> float:
        value = self.axes.get(axis, 0.0)
        if abs(value) < dead_zone:
            return 0.0
        return value


class GamepadController:
    def __init__(self, manager: "PeripheralManager", debug_tap: InputDebugTap) -> None:
        self._manager = manager
        self._debug_tap = debug_tap
        self._last_pump_monotonic = 0.0
        self._stats_window_start = time.monotonic()
        self._sample_calls = 0
        self._sample_events_calls = 0
        self._targeted_sample_calls = 0
        self._gamepad_slots_sampled = 0
        self._connected_snapshots_sampled = 0
        self._pump_calls = 0
        self._pump_skips = 0
        self._pump_errors = 0
        self._sample_callers: dict[str, int] = {}
        self._input_events = input_event_topic()
        self._state = gamepad_state_topic()

    def input_events(self) -> Any:
        return self._input_events

    def poll(self) -> tuple[GamepadSnapshotEvent, ...]:
        events = self.sample(source="runtime.input")
        timestamp = max(
            (event.snapshot.timestamp_monotonic for event in events),
            default=time.monotonic(),
        )
        self._state.publish(
            GamepadInputState(
                snapshots_json=json.dumps(
                    [_snapshot_event_payload(event) for event in events],
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                timestamp_monotonic=timestamp,
            )
        )
        return events

    def latest(self) -> tuple[GamepadSnapshotEvent, ...]:
        row = self._state.latest()
        if row is None:
            return ()
        return _snapshot_events_from_row(row)

    def state_stream(self) -> Any:
        return self._state.map(_snapshot_events_from_row)

    def sample(
        self,
        joystick_id: int | None = None,
        *,
        include_tapped_buttons: bool = True,
        source: str = "direct.sample",
    ) -> tuple[GamepadSnapshotEvent, ...]:
        self._pump_gamepad_events()
        if joystick_id is not None:
            gamepad = self._gamepad(joystick_id)
            if gamepad is None:
                self._record_sample(
                    kind="sample",
                    joystick_id=joystick_id,
                    gamepad_count=0,
                    connected_count=0,
                    source=source,
                )
                return ()
            snapshot = self._sample_gamepad(
                gamepad,
                include_tapped_buttons=include_tapped_buttons,
            )
            if not snapshot.connected:
                self._record_sample(
                    kind="sample",
                    joystick_id=joystick_id,
                    gamepad_count=1,
                    connected_count=0,
                    source=source,
                )
                return ()
            self._record_sample(
                kind="sample",
                joystick_id=joystick_id,
                gamepad_count=1,
                connected_count=1,
                source=source,
            )
            events = (GamepadSnapshotEvent(joystick_id=joystick_id, snapshot=snapshot),)
            self._publish_snapshot_events(events, source=source)
            return events
        gamepads = self._gamepads()
        events = self._sample_events_without_pump(
            gamepads=gamepads,
            include_tapped_buttons=include_tapped_buttons,
        )
        self._record_sample(
            kind="sample",
            joystick_id=None,
            gamepad_count=len(gamepads),
            connected_count=len(events),
            source=source,
        )
        self._publish_snapshot_events(events, source=source)
        return events

    def sample_events(
        self,
        *,
        include_tapped_buttons: bool = True,
        source: str = "direct.sample_events",
    ) -> tuple[GamepadSnapshotEvent, ...]:
        self._pump_gamepad_events()
        gamepads = self._gamepads()
        events = self._sample_events_without_pump(
            gamepads=gamepads,
            include_tapped_buttons=include_tapped_buttons,
        )
        self._record_sample(
            kind="sample_events",
            joystick_id=None,
            gamepad_count=len(gamepads),
            connected_count=len(events),
            source=source,
        )
        self._publish_snapshot_events(events, source=source)
        return events

    def _sample_events_without_pump(
        self,
        *,
        gamepads: tuple[Gamepad, ...] | None = None,
        include_tapped_buttons: bool = True,
    ) -> tuple[GamepadSnapshotEvent, ...]:
        events: list[GamepadSnapshotEvent] = []
        for gamepad in gamepads if gamepads is not None else self._gamepads():
            snapshot = self._sample_gamepad(
                gamepad,
                include_tapped_buttons=include_tapped_buttons,
            )
            if snapshot.connected:
                events.append(
                    GamepadSnapshotEvent(
                        joystick_id=screen_slot_for_joystick(gamepad.joystick_id),
                        snapshot=snapshot,
                    )
                )
        return tuple(events)

    def _sample_gamepad(
        self,
        gamepad: Gamepad,
        *,
        include_tapped_buttons: bool = True,
    ) -> GamepadSnapshot:
        gamepad.update(pump_events=False)
        if not gamepad.is_connected():
            return GamepadSnapshot(
                connected=False, identifier=None, timestamp_monotonic=time.monotonic()
            )
        mapping = self._mapping_for_gamepad(gamepad)
        buttons = {
            GamepadButton.SOUTH: gamepad.is_held(mapping.BUTTON_B),
            GamepadButton.EAST: gamepad.is_held(mapping.BUTTON_A),
            GamepadButton.WEST: gamepad.is_held(mapping.BUTTON_Y),
            GamepadButton.NORTH: gamepad.is_held(mapping.BUTTON_X),
            GamepadButton.PLUS: gamepad.is_held(mapping.BUTTON_PLUS),
            GamepadButton.MINUS: gamepad.is_held(mapping.BUTTON_MINUS),
            GamepadButton.HOME: gamepad.is_held(mapping.BUTTON_HOME),
            GamepadButton.CAPTURE: mapping.BUTTON_CAPTURE >= 0
            and gamepad.is_held(mapping.BUTTON_CAPTURE),
            GamepadButton.ZL: gamepad.is_held(mapping.BUTTON_ZL),
            GamepadButton.ZR: gamepad.is_held(mapping.BUTTON_ZR),
            GamepadButton.L3: gamepad.is_held(mapping.BUTTON_L3),
            GamepadButton.R3: gamepad.is_held(mapping.BUTTON_R3),
        }
        tapped_buttons = frozenset()
        if include_tapped_buttons:
            tapped_buttons = frozenset(
                button
                for button, button_id_for in GAMEPAD_BUTTON_MAPPING_ACCESSORS
                if (button_id := button_id_for(mapping)) >= 0
                and gamepad.was_tapped(button_id)
            )
        axes = {
            GamepadAxis.LEFT_X: gamepad.axis_value(mapping.AXIS_LEFT_X, dead_zone=0.0),
            GamepadAxis.LEFT_Y: gamepad.axis_value(mapping.AXIS_LEFT_Y, dead_zone=0.0),
            GamepadAxis.RIGHT_X: gamepad.axis_value(
                mapping.AXIS_RIGHT_X, dead_zone=0.0
            ),
            GamepadAxis.RIGHT_Y: gamepad.axis_value(
                mapping.AXIS_RIGHT_Y, dead_zone=0.0
            ),
            GamepadAxis.TRIGGER_LEFT: gamepad.axis_value(mapping.AXIS_L, dead_zone=0.0),
            GamepadAxis.TRIGGER_RIGHT: gamepad.axis_value(
                mapping.AXIS_R, dead_zone=0.0
            ),
        }
        dpad = self._read_dpad(gamepad, mapping)
        return GamepadSnapshot(
            connected=True,
            identifier=gamepad.gamepad_identifier.value,
            buttons=buttons,
            tapped_buttons=tapped_buttons,
            axes=axes,
            dpad=dpad,
            timestamp_monotonic=time.monotonic(),
        )

    def _gamepads(self) -> tuple[Gamepad, ...]:
        gamepads: list[Gamepad] = []
        for peripheral in self._manager.peripherals:
            if isinstance(peripheral, Gamepad):
                gamepads.append(peripheral)
        return tuple(gamepads)

    def _pump_gamepad_events(self) -> None:
        now = time.monotonic()
        if now - self._last_pump_monotonic < GAMEPAD_PUMP_THROTTLE_SECONDS:
            self._pump_skips += 1
            return
        try:
            pygame.event.pump()
        except pygame.error:
            self._pump_errors += 1
            return
        self._pump_calls += 1
        self._last_pump_monotonic = now

    def _record_sample(
        self,
        *,
        kind: str,
        joystick_id: int | None,
        gamepad_count: int,
        connected_count: int,
        source: str,
    ) -> None:
        if kind == "sample_events":
            self._sample_events_calls += 1
        else:
            self._sample_calls += 1
        if joystick_id is not None:
            self._targeted_sample_calls += 1
        self._gamepad_slots_sampled += gamepad_count
        self._connected_snapshots_sampled += connected_count
        self._sample_callers[source] = self._sample_callers.get(source, 0) + 1
        self._log_sample_stats_if_due()

    def _publish_snapshot_events(
        self,
        events: tuple[GamepadSnapshotEvent, ...],
        *,
        source: str,
    ) -> None:
        for event in events:
            self._input_events.publish(
                InputEvent.from_payload(
                    event_type="input.raw.gamepad.snapshot",
                    source_id=f"gamepad.{event.joystick_id}",
                    stream_name="gamepad.snapshot",
                    stage="raw",
                    payload={
                        "source": source,
                        "joystick_id": event.joystick_id,
                        "snapshot": event.snapshot,
                    },
                    timestamp_monotonic=event.snapshot.timestamp_monotonic,
                )
            )

    def _log_sample_stats_if_due(self) -> None:
        now = time.monotonic()
        elapsed = now - self._stats_window_start
        if elapsed < GAMEPAD_STATS_LOG_INTERVAL_SECONDS:
            return
        total_calls = self._sample_calls + self._sample_events_calls
        if total_calls == 0:
            self._reset_sample_stats(now)
            return
        top_callers = ", ".join(
            f"{caller}={count}"
            for caller, count in sorted(
                self._sample_callers.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
        )
        logger.info(
            "Gamepad sample stats window=%.1fs sample_calls=%d "
            "sample_events_calls=%d targeted_calls=%d slots_sampled=%d "
            "connected_snapshots=%d pump_calls=%d pump_skips=%d "
            "pump_errors=%d top_callers=%s",
            elapsed,
            self._sample_calls,
            self._sample_events_calls,
            self._targeted_sample_calls,
            self._gamepad_slots_sampled,
            self._connected_snapshots_sampled,
            self._pump_calls,
            self._pump_skips,
            self._pump_errors,
            top_callers or "none",
        )
        self._reset_sample_stats(now)

    def _reset_sample_stats(self, now: float) -> None:
        self._stats_window_start = now
        self._sample_calls = 0
        self._sample_events_calls = 0
        self._targeted_sample_calls = 0
        self._gamepad_slots_sampled = 0
        self._connected_snapshots_sampled = 0
        self._pump_calls = 0
        self._pump_skips = 0
        self._pump_errors = 0
        self._sample_callers.clear()

    def _gamepad(self, joystick_id: int) -> Gamepad | None:
        for gamepad in self._gamepads():
            if gamepad.joystick_id == joystick_id:
                return gamepad
        return None

    def _snapshot_for_joystick_id(self, joystick_id: int) -> GamepadSnapshot:
        events = self.sample(
            joystick_id=joystick_id,
            include_tapped_buttons=False,
            source="gamepad.snapshot_for_joystick_id",
        )
        if not events:
            return GamepadSnapshot(connected=False, identifier=None)
        return events[0].snapshot

    @staticmethod
    def _mapping_for_gamepad(gamepad: Gamepad) -> SwitchLikeMapping:
        identifier = gamepad.gamepad_identifier
        if identifier is GamepadIdentifier.SWITCH_PRO:
            return SwitchProMapping()
        if Configuration.is_pi():
            return BitDoLite2Bluetooth()
        return BitDoLite2()

    @staticmethod
    def _read_dpad(gamepad: Gamepad, mapping: SwitchLikeMapping) -> GamepadDpadValue:
        if mapping.get_dpad_type() is DpadType.HAT and gamepad.joystick is not None:
            hat_index = mapping.DPAD_HAT
            if hat_index is None or hat_index < 0:
                return GamepadDpadValue()
            try:
                x_dir, y_dir = gamepad.joystick.get_hat(hat_index)
            except pygame.error:
                return GamepadDpadValue()
            return GamepadDpadValue(x=int(x_dir), y=int(y_dir))
        if mapping.get_dpad_type() is DpadType.BUTTONS:
            x_dir = int(gamepad.is_held(mapping.DPAD_RIGHT)) - int(
                gamepad.is_held(mapping.DPAD_LEFT)
            )
            y_dir = int(gamepad.is_held(mapping.DPAD_UP)) - int(
                gamepad.is_held(mapping.DPAD_DOWN)
            )
            return GamepadDpadValue(x=x_dir, y=y_dir)
        return GamepadDpadValue()


def _snapshot_event_payload(event: GamepadSnapshotEvent) -> dict[str, Any]:
    snapshot = event.snapshot
    return {
        "joystick_id": event.joystick_id,
        "connected": snapshot.connected,
        "identifier": snapshot.identifier,
        "buttons": {button.value: held for button, held in snapshot.buttons.items()},
        "tapped_buttons": sorted(button.value for button in snapshot.tapped_buttons),
        "axes": {axis.value: value for axis, value in snapshot.axes.items()},
        "dpad_x": snapshot.dpad.x,
        "dpad_y": snapshot.dpad.y,
        "timestamp_monotonic": snapshot.timestamp_monotonic,
    }


def _snapshot_event_from_payload(payload: dict[str, Any]) -> GamepadSnapshotEvent:
    return GamepadSnapshotEvent(
        joystick_id=int(payload["joystick_id"]),
        snapshot=GamepadSnapshot(
            connected=bool(payload["connected"]),
            identifier=payload.get("identifier"),
            buttons={
                GamepadButton(button): bool(held)
                for button, held in payload.get("buttons", {}).items()
            },
            tapped_buttons=frozenset(
                GamepadButton(button) for button in payload.get("tapped_buttons", ())
            ),
            axes={
                GamepadAxis(axis): float(value)
                for axis, value in payload.get("axes", {}).items()
            },
            dpad=GamepadDpadValue(
                x=int(payload.get("dpad_x", 0)),
                y=int(payload.get("dpad_y", 0)),
            ),
            timestamp_monotonic=float(payload.get("timestamp_monotonic", 0.0)),
        ),
    )


def _snapshot_events_from_row(row: Any) -> tuple[GamepadSnapshotEvent, ...]:
    return tuple(
        _snapshot_event_from_payload(payload)
        for payload in json.loads(str(row.snapshots_json))
    )

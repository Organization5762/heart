from __future__ import annotations

import json
import time
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Any, cast

import pygame
from manyfold import Subscribable
from manyfold.architecture import NewValues

from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.events import (KeyboardInputState,
                                                keyboard_state_topic)
from heart.peripheral.core.input.streams import scan_stream
from heart.peripheral.keyboard import (KeyboardEvent, KeyHeldEvent,
                                       KeyPressedEvent, KeyReleasedEvent,
                                       KeyState)
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

KEYBOARD_RELEASE_DEBOUNCE_MS = 60.0
NON_INDEX_KEY_CODES = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT)
logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class KeyboardSnapshot:
    pressed_keys: frozenset[int]
    timestamp_ms: float


@dataclass(frozen=True, slots=True)
class _KeyboardTracker:
    state: KeyState = KeyState()
    event: KeyboardEvent | None = None


class KeyboardController:
    def __init__(self, debug_tap: InputDebugTap) -> None:
        self._debug_tap = debug_tap
        self._key_event_subscriptions: dict[int, object] = {}
        self._state = keyboard_state_topic()

    @cached_property
    def _snapshot_stream(self) -> Subscribable[KeyboardSnapshot]:
        stream = self._state.map(_keyboard_snapshot_from_row)
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="keyboard.snapshot",
            source_id="keyboard",
        ).connect(stream)

    def snapshot_stream(self) -> Subscribable[KeyboardSnapshot]:
        return self._snapshot_stream

    def poll(self) -> KeyboardSnapshot:
        snapshot = self.sample()
        self._state.publish(
            KeyboardInputState(
                pressed_keys_json=json.dumps(sorted(snapshot.pressed_keys)),
                timestamp_ms=snapshot.timestamp_ms,
            )
        )
        return snapshot

    def latest(self) -> KeyboardSnapshot:
        row = self._state.latest()
        if row is None:
            return KeyboardSnapshot(
                pressed_keys=frozenset(),
                timestamp_ms=0.0,
            )
        return _keyboard_snapshot_from_row(row)

    def close(self) -> None:
        for subscription in self._key_event_subscriptions.values():
            subscription.dispose()
        self._key_event_subscriptions.clear()

    def sample(self) -> KeyboardSnapshot:
        if Configuration.is_pi() and (not Configuration.is_x11_forward()):
            return KeyboardSnapshot(
                pressed_keys=frozenset(), timestamp_ms=time.monotonic() * 1000.0
            )
        try:
            pygame.event.pump()
            keys = pygame.key.get_pressed()
        except pygame.error:
            logger.debug(
                "Keyboard polling skipped because pygame video is unavailable."
            )
            return KeyboardSnapshot(
                pressed_keys=frozenset(), timestamp_ms=time.monotonic() * 1000.0
            )
        return KeyboardSnapshot(
            pressed_keys=_pressed_keys_from_state(keys),
            timestamp_ms=time.monotonic() * 1000.0,
        )

    @cache
    def key_events(self, key: int) -> Subscribable[KeyboardEvent]:
        def _advance(
            tracker: _KeyboardTracker, snapshot: KeyboardSnapshot
        ) -> _KeyboardTracker:
            pressed = key in snapshot.pressed_keys
            current = tracker.state
            now = snapshot.timestamp_ms
            key_name = pygame.key.name(key)
            event: KeyboardEvent | None = None
            if pressed:
                if not current.pressed:
                    updated = KeyState(pressed=True, held=False, last_change_ms=now)
                    event = KeyPressedEvent(
                        key=key, key_name=key_name, state=updated, timestamp_ms=now
                    )
                elif not current.held:
                    updated = KeyState(pressed=True, held=True, last_change_ms=now)
                    event = KeyHeldEvent(
                        key=key, key_name=key_name, state=updated, timestamp_ms=now
                    )
                else:
                    updated = current
            else:
                if (
                    current.pressed
                    and now - current.last_change_ms < KEYBOARD_RELEASE_DEBOUNCE_MS
                ):
                    return _KeyboardTracker(state=current, event=None)
                if current.pressed or current.held:
                    updated = KeyState(pressed=False, held=False, last_change_ms=now)
                    event = KeyReleasedEvent(
                        key=key, key_name=key_name, state=updated, timestamp_ms=now
                    )
                else:
                    updated = current
            if isinstance(event, KeyPressedEvent):
                logger.info(
                    "Keyboard key pressed: key=%s code=%s timestamp_ms=%.1f",
                    key_name,
                    key,
                    now,
                )
            elif isinstance(event, KeyReleasedEvent):
                logger.info(
                    "Keyboard key released: key=%s code=%s timestamp_ms=%.1f",
                    key_name,
                    key,
                    now,
                )
            return _KeyboardTracker(state=updated, event=event)

        base_stream = (
            scan_stream(
                self.snapshot_stream(),
                _advance,
                seed=_KeyboardTracker(),
            )
            .map(lambda tracker: tracker.event)
            .filter(lambda event: event is not None)
            .map(lambda event: cast(KeyboardEvent, event))
        )
        events = NewValues[KeyboardEvent](
            name=f"heart.input.keyboard.key.{pygame.key.name(key)}"
        )
        instrumented = InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name=f"keyboard.key.{pygame.key.name(key)}",
            source_id=lambda event: cast(KeyboardEvent, event).key_name,
            upstream_ids=("keyboard.snapshot",),
        ).connect(base_stream)
        self._key_event_subscriptions[key] = instrumented.subscribe(events.publish)
        return events

    @cache
    def key_pressed(self, key: int) -> Subscribable[KeyPressedEvent]:
        return self._key_view(key, event_type=KeyPressedEvent, suffix="pressed")

    @cache
    def key_released(self, key: int) -> Subscribable[KeyReleasedEvent]:
        return self._key_view(key, event_type=KeyReleasedEvent, suffix="released")

    @cache
    def key_held(self, key: int) -> Subscribable[KeyHeldEvent]:
        return self._key_view(key, event_type=KeyHeldEvent, suffix="held")

    @cache
    def key_state(self, key: int) -> Subscribable[KeyState]:
        stream = (
            self.key_events(key)
            .map(lambda event: event.state)
            .start_with(KeyState())
            .distinct_until_changed()
        )
        key_name = pygame.key.name(key)
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"keyboard.key_state.{key_name}",
            source_id=key_name,
            upstream_ids=(f"keyboard.key.{key_name}",),
        ).connect(stream)

    def _key_view(
        self,
        key: int,
        *,
        event_type: type[KeyPressedEvent] | type[KeyReleasedEvent] | type[KeyHeldEvent],
        suffix: str,
    ) -> Subscribable[KeyPressedEvent | KeyReleasedEvent | KeyHeldEvent]:
        key_name = pygame.key.name(key)
        stream = (
            self.key_events(key)
            .filter(lambda event: isinstance(event, event_type))
            .map(
                lambda event: cast(
                    KeyPressedEvent | KeyReleasedEvent | KeyHeldEvent, event
                )
            )
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"keyboard.{suffix}.{key_name}",
            source_id=key_name,
            upstream_ids=(f"keyboard.key.{key_name}",),
        ).connect(stream)


def _pressed_keys_from_state(keys: Any) -> frozenset[int]:
    """Normalize pygame key state into key constants used by input profiles."""
    pressed: set[int] = set()
    for index in range(len(keys)):
        if _is_pressed(keys, index):
            pressed.add(index)
    for key_code in NON_INDEX_KEY_CODES:
        if _is_pressed(keys, key_code):
            pressed.add(key_code)
    return frozenset(pressed)


def _is_pressed(keys: Any, key: int) -> bool:
    try:
        return bool(keys[key])
    except (IndexError, KeyError):
        return False


def _keyboard_snapshot_from_row(row: Any) -> KeyboardSnapshot:
    return KeyboardSnapshot(
        pressed_keys=frozenset(json.loads(str(row.pressed_keys_json))),
        timestamp_ms=float(row.timestamp_ms),
    )

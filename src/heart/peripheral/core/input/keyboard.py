from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import timedelta
from functools import cache, cached_property
from typing import cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.input.debug import (InputDebugStage, InputDebugTap,
                                               instrument_input_stream)
from heart.peripheral.keyboard import KeyboardAction, KeyboardEvent, KeyState
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import (input_scheduler,
                                               interval_in_background,
                                               pipe_in_background,
                                               pipe_in_main_thread)

KEYBOARD_POLL_INTERVAL_MS = 5
KEYBOARD_RELEASE_DEBOUNCE_MS = 60.0
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

    @cached_property
    def _snapshot_stream(self) -> reactivex.Observable[KeyboardSnapshot]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            return cast(reactivex.Observable[KeyboardSnapshot], reactivex.empty())

        def _sample(_: int) -> KeyboardSnapshot:
            try:
                keys = pygame.key.get_pressed()
            except pygame.error:
                logger.debug(
                    "Keyboard polling skipped because pygame video is unavailable."
                )
                return KeyboardSnapshot(
                    pressed_keys=frozenset(),
                    timestamp_ms=time.monotonic() * 1000.0,
                )
            pressed = frozenset(
                index for index in range(len(keys)) if keys[index]
            )
            return KeyboardSnapshot(
                pressed_keys=pressed,
                timestamp_ms=time.monotonic() * 1000.0,
            )

        stream = pipe_in_main_thread(
            interval_in_background(
                period=timedelta(milliseconds=KEYBOARD_POLL_INTERVAL_MS),
                scheduler=input_scheduler(),
            ),
            ops.map(_sample),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="keyboard.snapshot",
            source_id="keyboard",
        )

    def snapshot_stream(self) -> reactivex.Observable[KeyboardSnapshot]:
        return self._snapshot_stream

    @cache
    def key_events(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        def _advance(
            tracker: _KeyboardTracker,
            snapshot: KeyboardSnapshot,
        ) -> _KeyboardTracker:
            pressed = key in snapshot.pressed_keys
            current = tracker.state
            now = snapshot.timestamp_ms
            key_name = pygame.key.name(key)
            event: KeyboardEvent | None = None

            if pressed:
                if not current.pressed:
                    updated = KeyState(pressed=True, held=False, last_change_ms=now)
                    event = KeyboardEvent(
                        key=key,
                        key_name=key_name,
                        action=KeyboardAction.PRESSED,
                        state=updated,
                        timestamp_ms=now,
                    )
                elif not current.held:
                    updated = KeyState(pressed=True, held=True, last_change_ms=now)
                    event = KeyboardEvent(
                        key=key,
                        key_name=key_name,
                        action=KeyboardAction.HELD,
                        state=updated,
                        timestamp_ms=now,
                    )
                else:
                    updated = current
            else:
                if current.pressed and (now - current.last_change_ms < KEYBOARD_RELEASE_DEBOUNCE_MS):
                    return _KeyboardTracker(state=current, event=None)
                if current.pressed or current.held:
                    updated = KeyState(pressed=False, held=False, last_change_ms=now)
                    event = KeyboardEvent(
                        key=key,
                        key_name=key_name,
                        action=KeyboardAction.RELEASED,
                        state=updated,
                        timestamp_ms=now,
                    )
                else:
                    updated = current

            return _KeyboardTracker(state=updated, event=event)

        base_stream = pipe_in_background(
            self.snapshot_stream(),
            ops.scan(_advance, seed=_KeyboardTracker()),
            ops.map(lambda tracker: tracker.event),
            ops.filter(lambda event: event is not None),
            ops.map(lambda event: cast(KeyboardEvent, event)),
        )
        return instrument_input_stream(
            base_stream,
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name=f"keyboard.key.{pygame.key.name(key)}",
            source_id=lambda event: cast(KeyboardEvent, event).key_name,
            upstream_ids=("keyboard.snapshot",),
        )

    @cache
    def key_pressed(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        return self._key_view(
            key,
            action=KeyboardAction.PRESSED,
            suffix="pressed",
        )

    @cache
    def key_released(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        return self._key_view(
            key,
            action=KeyboardAction.RELEASED,
            suffix="released",
        )

    @cache
    def key_held(self, key: int) -> reactivex.Observable[KeyboardEvent]:
        return self._key_view(
            key,
            action=KeyboardAction.HELD,
            suffix="held",
        )

    @cache
    def key_state(self, key: int) -> reactivex.Observable[KeyState]:
        stream = pipe_in_background(
            self.key_events(key),
            ops.map(lambda event: event.state),
            ops.start_with(KeyState()),
            ops.distinct_until_changed(),
        )
        key_name = pygame.key.name(key)
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"keyboard.key_state.{key_name}",
            source_id=key_name,
            upstream_ids=(f"keyboard.key.{key_name}",),
        )

    def _key_view(
        self,
        key: int,
        *,
        action: KeyboardAction,
        suffix: str,
    ) -> reactivex.Observable[KeyboardEvent]:
        key_name = pygame.key.name(key)
        stream = pipe_in_background(
            self.key_events(key),
            ops.filter(lambda event: event.action is action),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"keyboard.{suffix}.{key_name}",
            source_id=key_name,
            upstream_ids=(f"keyboard.key.{key_name}",),
        )

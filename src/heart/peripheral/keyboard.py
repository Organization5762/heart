import time
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from functools import cache
from typing import Any, Iterator, Self, cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Peripheral
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import input_scheduler

logger = get_logger(__name__)

class KeyboardAction(StrEnum):
    PRESSED = "pressed"
    HELD = "held"
    RELEASED = "released"


@dataclass(frozen=True, slots=True)
class KeyState:
    pressed: bool = False
    held: bool = False
    last_change_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class KeyboardEvent:
    key: int
    key_name: str
    action: KeyboardAction
    state: KeyState
    timestamp_ms: float


class KeyboardKey(Peripheral[KeyboardEvent]):
    def __init__(self, key: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.key = key
        self.state = KeyState()

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield from [
            cls.get(pygame.K_UP),
            cls.get(pygame.K_DOWN),
            cls.get(pygame.K_LEFT),
            cls.get(pygame.K_RIGHT)
        ]

    @classmethod
    @cache
    def get(cls, key: int) -> Self:
        return cls(key)

    def _event_stream(self) -> reactivex.Observable[KeyboardEvent]:
        """
        Periodically sample keyboard state as KeyboardEvent edges.

        On Pi without X11 we emit an empty observable (no events).
        """

        def _poll(_: int) -> KeyboardEvent | None:
            result = self._check_if_pressed()
            return result

        if Configuration.is_pi() and not Configuration.is_x11_forward():
            # empty() is typed as Observable[NoReturn | Never] so we cast it
            # to keep type checkers happy about the return type.
            return cast(reactivex.Observable[KeyboardEvent], reactivex.empty())

        return reactivex.interval(
            timedelta(milliseconds=5),
            scheduler=input_scheduler(),
        ).pipe(
            ops.map(_poll),
            ops.filter(lambda event: event is not None),
            ops.map(lambda event: cast(KeyboardEvent, event)),
            ops.share(),
        )

    def _check_if_pressed(self) -> KeyboardEvent | None:
        keys = pygame.key.get_pressed()
        now = time.monotonic() * 1000
        current = self.state
        event: KeyboardEvent | None = None
        key_name = pygame.key.name(self.key)

        if keys[self.key]:
            if not current.pressed:
                updated = KeyState(pressed=True, held=False, last_change_ms=now)
                event = KeyboardEvent(
                    key=self.key,
                    key_name=key_name,
                    action=KeyboardAction.PRESSED,
                    state=updated,
                    timestamp_ms=now,
                )
            elif not current.held:
                updated = KeyState(pressed=True, held=True, last_change_ms=now)
                event = KeyboardEvent(
                    key=self.key,
                    key_name=key_name,
                    action=KeyboardAction.HELD,
                    state=updated,
                    timestamp_ms=now,
                )
            else:
                updated = current
        else:
            if current.pressed and (now - current.last_change_ms < 60):
                return None
            if current.pressed or current.held:
                updated = KeyState(pressed=False, held=False, last_change_ms=now)
                event = KeyboardEvent(
                    key=self.key,
                    key_name=key_name,
                    action=KeyboardAction.RELEASED,
                    state=updated,
                    timestamp_ms=now,
                )
            else:
                updated = current

        self.state = updated
        return event

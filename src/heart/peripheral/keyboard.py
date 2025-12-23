import time
from dataclasses import dataclass
from datetime import timedelta
from functools import cache
from typing import Any, Iterator, Self, cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Peripheral
from heart.utilities.env import Configuration
from heart.utilities.reactivex_threads import input_scheduler


@dataclass
class KeyTimeline:
    pressed: bool = False
    held: bool = False
    last_change_ts: float = 0

    def first_press(self) -> bool:
        return self.pressed and not self.held



class KeyboardKey(Peripheral[KeyTimeline]):
    def __init__(self, key: int, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.key = key
        self.state = KeyTimeline()

        # Start running the key checker
        if not (Configuration.is_pi() and not Configuration.is_x11_forward()):
            scheduler = input_scheduler()
            check_for_input = reactivex.interval(
                timedelta(milliseconds=10), scheduler=scheduler
            )
            check_for_input.subscribe(
                on_next=lambda _: self._check_if_pressed(),
                scheduler=scheduler,
            )

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

    def _snapshot(self) -> KeyTimeline:
        return self.state

    def _event_stream(self) -> reactivex.Observable[KeyTimeline]:
        """
        Periodically sample keyboard state as a KeyTimeline.

        On Pi without X11 we emit an empty observable (no events).
        """

        def _generate(_: int) -> KeyTimeline:
            # interval emits an int tick count; we ignore it and just snapshot.
            snapshot: KeyTimeline = self._snapshot()
            return snapshot

        def only_keypress(x: KeyTimeline) -> bool:
            return x.first_press()

        if Configuration.is_pi() and not Configuration.is_x11_forward():
            # empty() is typed as Observable[NoReturn | Never] so we cast it
            # to keep type checkers happy about the return type.
            return cast(reactivex.Observable[KeyTimeline], reactivex.empty())

        return (
            reactivex.interval(
                timedelta(milliseconds=5),
                scheduler=input_scheduler(),
            )
            .pipe(
                ops.map(_generate),  # Observable[KeyTimeline]
                ops.distinct_until_changed(only_keypress),
                ops.share(),
            )
        )

    def _check_if_pressed(self) -> None:
        keys = pygame.key.get_pressed()
        now = time.time() * 1000

        def check_with_cache(key: int, s: KeyTimeline) -> KeyTimeline:
            # Is pressed
            if keys[key]:
                if s.pressed:
                    s.held = True
                s.last_change_ts = now
                s.pressed = True
                return s
            elif s.pressed and (now - s.last_change_ts < 60):
                return s
            else:
                s.pressed = False
                s.held = False
                return s

        self.state = check_with_cache(self.key, self.state)

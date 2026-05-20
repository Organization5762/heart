from __future__ import annotations

import time

import pygame

from heart.peripheral.core import events
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
GLOBAL_EVENT_TYPES = (
    pygame.QUIT,
    events.REQUEST_JOYSTICK_MODULE_RESET,
)
EVENT_HANDLER_STATS_LOG_INTERVAL_SECONDS = 5.0
BLOCKED_JOYSTICK_EVENT_TYPES = (
    pygame.JOYAXISMOTION,
    pygame.JOYBALLMOTION,
    pygame.JOYHATMOTION,
    pygame.JOYBUTTONDOWN,
    pygame.JOYBUTTONUP,
)


class PygameEventHandler:
    def __init__(self) -> None:
        self._blocked_joystick_events = False
        self._stats_window_start = time.monotonic()
        self._handle_calls = 0
        self._events_seen = 0
        self._quit_events = 0
        self._joystick_reset_events = 0
        self._system_errors = 0

    def handle_events(self) -> bool:
        running = True
        self._handle_calls += 1
        self._ensure_joystick_events_blocked()
        try:
            for event in pygame.event.get(GLOBAL_EVENT_TYPES):
                self._events_seen += 1
                if event.type == pygame.QUIT:
                    self._quit_events += 1
                    running = False
                elif event.type == events.REQUEST_JOYSTICK_MODULE_RESET:
                    self._joystick_reset_events += 1
                    logger.info("resetting joystick module")
                    pygame.joystick.quit()
                    pygame.joystick.init()
        except SystemError:
            self._system_errors += 1
            # (clem): gamepad shit is weird and can randomly put caught segfault
            #   events on queue, I see allusions to this online, people say
            #   try pygame-ce instead
            logger.exception("Encountered segfaulted event")
        self._log_stats_if_due()
        return running

    def _ensure_joystick_events_blocked(self) -> None:
        if self._blocked_joystick_events:
            return
        try:
            pygame.event.set_blocked(BLOCKED_JOYSTICK_EVENT_TYPES)
        except pygame.error:
            return
        self._blocked_joystick_events = True
        logger.info("Blocked queued pygame joystick events")

    def _log_stats_if_due(self) -> None:
        now = time.monotonic()
        elapsed = now - self._stats_window_start
        if elapsed < EVENT_HANDLER_STATS_LOG_INTERVAL_SECONDS:
            return
        logger.info(
            "Pygame event stats window=%.1fs handle_calls=%d events_seen=%d "
            "quit_events=%d joystick_reset_events=%d system_errors=%d",
            elapsed,
            self._handle_calls,
            self._events_seen,
            self._quit_events,
            self._joystick_reset_events,
            self._system_errors,
        )
        self._stats_window_start = now
        self._handle_calls = 0
        self._events_seen = 0
        self._quit_events = 0
        self._joystick_reset_events = 0
        self._system_errors = 0

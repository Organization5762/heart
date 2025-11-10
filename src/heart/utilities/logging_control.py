from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from functools import cache
from typing import Callable, Sequence

LOG_RULES_ENV_VAR = "HEART_LOG_RULES"
DEFAULT_INTERVAL_ENV_VAR = "HEART_LOG_DEFAULT_INTERVAL"
DEFAULT_FALLBACK_LEVEL = logging.DEBUG
DEFAULT_INTERVAL_SECONDS = 1.0

_RULE_PATTERN = re.compile(
    r"^(?P<key>[^=]+)="
    r"(?P<interval>none|\d+(?:\.\d+)?)"
    r"(?::(?P<level>[A-Za-z]+))?"
    r"(?::(?P<fallback>[A-Za-z]+|none))?$"
)


@dataclass(frozen=True)
class LogRule:
    """Configuration describing how frequently to emit a log statement."""

    interval_seconds: float | None
    level: int | None
    fallback_level: int | None


class LoggingController:
    """Centralised control for log sampling and verbosity overrides."""

    def __init__(
        self,
        *,
        default_interval: float | None,
        default_fallback_level: int | None,
        rules: dict[str, LogRule],
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._default_interval = default_interval
        self._default_fallback_level = default_fallback_level
        self._rules = rules
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._next_emit: dict[str, float] = {}

    def _rule_for(self, key: str) -> LogRule:
        if key in self._rules:
            return self._rules[key]
        return LogRule(
            interval_seconds=self._default_interval,
            level=None,
            fallback_level=self._default_fallback_level,
        )

    def log(
        self,
        *,
        key: str,
        logger: logging.Logger,
        level: int,
        msg: str,
        args: Sequence[object] | None = None,
        extra: dict[str, object] | None = None,
        fallback_level: int | None = None,
    ) -> bool:
        """
        Emit a log statement honouring the configured sampling policy.

        Returns ``True`` if the primary log level was emitted, ``False`` otherwise.
        """

        rule = self._rule_for(key)
        primary_level = rule.level or level
        suppressed_level = (
            rule.fallback_level
            if rule.fallback_level is not None
            else fallback_level
        )

        interval = rule.interval_seconds
        if interval is None:
            logger.log(primary_level, msg, *(args or ()), extra=extra)
            return True

        now = self._monotonic()

        with self._lock:
            next_emit = self._next_emit.get(key, 0.0)
            if now >= next_emit:
                self._next_emit[key] = now + interval
                logger.log(primary_level, msg, *(args or ()), extra=extra)
                return True

        if suppressed_level is not None:
            logger.log(suppressed_level, msg, *(args or ()), extra=extra)
        return False


def _parse_level(name: str | None) -> int | None:
    if not name:
        return None
    resolved = getattr(logging, name.upper(), None)
    if isinstance(resolved, int):
        return resolved
    raise ValueError(f"Unknown log level {name!r}")


def _parse_interval(value: str) -> float | None:
    if value.lower() == "none":
        return None
    return float(value)


def _parse_rules(raw_rules: str) -> dict[str, LogRule]:
    rules: dict[str, LogRule] = {}
    for chunk in filter(None, (part.strip() for part in raw_rules.split(","))):
        match = _RULE_PATTERN.match(chunk)
        if not match:
            raise ValueError(
                "Invalid HEART_LOG_RULES entry. Expected 'key=interval[:LEVEL[:FALLBACK]]'."
            )
        key = match.group("key").strip()
        interval = _parse_interval(match.group("interval"))
        level = _parse_level(match.group("level"))
        fallback_raw = match.group("fallback")
        fallback_level = (
            None
            if fallback_raw is None
            else (None if fallback_raw.lower() == "none" else _parse_level(fallback_raw))
        )
        rules[key] = LogRule(interval, level, fallback_level)
    return rules


@cache
def get_logging_controller() -> LoggingController:
    """Return the shared logging controller instance."""

    default_interval_raw = os.getenv(DEFAULT_INTERVAL_ENV_VAR)
    default_interval = (
        DEFAULT_INTERVAL_SECONDS
        if default_interval_raw is None
        else _parse_interval(default_interval_raw)
    )

    rules_raw = os.getenv(LOG_RULES_ENV_VAR, "")
    rules = _parse_rules(rules_raw) if rules_raw else {}

    return LoggingController(
        default_interval=default_interval,
        default_fallback_level=DEFAULT_FALLBACK_LEVEL,
        rules=rules,
    )

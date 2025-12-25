from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from heart.utilities.env.parsing import _env_flag, _env_int, _env_optional_int
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class QueueOverflowStrategy(StrEnum):
    DROP_NEWEST = "drop_newest"
    DROP_OLDEST = "drop_oldest"
    ERROR = "error"


@dataclass(frozen=True)
class BeatsStreamingSettings:
    queue_max_size: int
    overflow_strategy: QueueOverflowStrategy
    json_sort_keys: bool
    json_indent: int | None


class BeatsStreamingConfiguration:
    @classmethod
    @cache
    def settings(cls) -> BeatsStreamingSettings:
        queue_max_size = _env_int("BEATS_STREAM_QUEUE_SIZE", default=256, minimum=1)
        overflow_strategy = cls._overflow_strategy()
        json_sort_keys = _env_flag("BEATS_STREAM_JSON_SORT_KEYS", default=True)
        json_indent = cls._json_indent()
        return BeatsStreamingSettings(
            queue_max_size=queue_max_size,
            overflow_strategy=overflow_strategy,
            json_sort_keys=json_sort_keys,
            json_indent=json_indent,
        )

    @classmethod
    def _overflow_strategy(cls) -> QueueOverflowStrategy:
        raw = os.environ.get("BEATS_STREAM_QUEUE_OVERFLOW", "drop_oldest").strip().lower()
        try:
            return QueueOverflowStrategy(raw)
        except ValueError as exc:
            options = ", ".join(strategy.value for strategy in QueueOverflowStrategy)
            raise ValueError(
                "BEATS_STREAM_QUEUE_OVERFLOW must be one of "
                f"{options}."
            ) from exc

    @classmethod
    def _json_indent(cls) -> int | None:
        raw = os.environ.get("BEATS_STREAM_JSON_INDENT")
        if raw is None:
            return None
        normalized = raw.strip().lower()
        if normalized in {"none", "null", "compact"}:
            return None
        try:
            return _env_optional_int("BEATS_STREAM_JSON_INDENT", minimum=0)
        except ValueError:
            logger.warning(
                "Invalid BEATS_STREAM_JSON_INDENT=%r; defaulting to compact JSON.",
                raw,
            )
            return None

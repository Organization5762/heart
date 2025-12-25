from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from functools import cache

from heart.utilities.env.parsing import _env_int


class QueueOverflowStrategy(StrEnum):
    DROP_NEWEST = "drop_newest"
    DROP_OLDEST = "drop_oldest"
    ERROR = "error"


@dataclass(frozen=True)
class BeatsStreamingSettings:
    queue_max_size: int
    overflow_strategy: QueueOverflowStrategy


class BeatsStreamingConfiguration:
    @classmethod
    @cache
    def settings(cls) -> BeatsStreamingSettings:
        queue_max_size = _env_int("BEATS_STREAM_QUEUE_SIZE", default=256, minimum=1)
        overflow_strategy = cls._overflow_strategy()
        return BeatsStreamingSettings(
            queue_max_size=queue_max_size,
            overflow_strategy=overflow_strategy,
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

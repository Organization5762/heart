from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum
from math import ceil
from typing import Any

import reactivex
from reactivex import operators as ops
from reactivex.subject import Subject

from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_DEBUG_HISTORY_SIZE = 512
DEFAULT_LATENCY_HISTORY_SIZE = 512


class InputDebugStage(StrEnum):
    RAW = "raw"
    VIEW = "view"
    LOGICAL = "logical"
    FRAME = "frame"


@dataclass(frozen=True, slots=True)
class InputDebugEnvelope:
    stage: InputDebugStage
    stream_name: str
    source_id: str
    timestamp_monotonic: float
    payload: Any
    upstream_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["stage"] = self.stage.value
        return payload


SourceResolver = str | Callable[[Any], str]


@dataclass(frozen=True, slots=True)
class InputLatencyStats:
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float


class InputDebugTap:
    """Record and broadcast traced input emissions for debugging and tests."""

    def __init__(
        self,
        history_size: int = DEFAULT_DEBUG_HISTORY_SIZE,
        latency_history_size: int = DEFAULT_LATENCY_HISTORY_SIZE,
    ) -> None:
        self._history_size = history_size
        self._latency_history_size = latency_history_size
        self._history: deque[InputDebugEnvelope] = deque(maxlen=history_size)
        self._latency_history: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._subject: Subject[InputDebugEnvelope] = Subject()

    def publish(
        self,
        *,
        stage: InputDebugStage,
        stream_name: str,
        source_id: str,
        payload: Any,
        upstream_ids: Iterable[str] = (),
    ) -> None:
        envelope = InputDebugEnvelope(
            stage=stage,
            stream_name=stream_name,
            source_id=source_id,
            timestamp_monotonic=time.monotonic(),
            payload=payload,
            upstream_ids=tuple(upstream_ids),
        )
        with self._lock:
            self._history.append(envelope)
        self._subject.on_next(envelope)

    def observable(self) -> reactivex.Observable[InputDebugEnvelope]:
        return pipe_in_background(self._subject)

    def snapshot(self) -> tuple[InputDebugEnvelope, ...]:
        with self._lock:
            return tuple(self._history)

    def record_latency(self, stream_name: str, delay_s: float) -> None:
        with self._lock:
            history = self._latency_history.setdefault(
                stream_name,
                deque(maxlen=self._latency_history_size),
            )
            history.append(max(delay_s, 0.0))

    def latency_snapshot(self) -> dict[str, InputLatencyStats]:
        with self._lock:
            snapshot = {
                stream_name: tuple(history)
                for stream_name, history in self._latency_history.items()
                if history
            }
        return {
            stream_name: _latency_stats(history)
            for stream_name, history in snapshot.items()
        }


def _latency_stats(history: tuple[float, ...]) -> InputLatencyStats:
    ordered = sorted(history)

    def percentile(rank: float) -> float:
        index = max(0, ceil(rank * len(ordered)) - 1)
        return ordered[index] * 1000.0

    return InputLatencyStats(
        count=len(ordered),
        p50_ms=percentile(0.50),
        p95_ms=percentile(0.95),
        p99_ms=percentile(0.99),
        max_ms=max(ordered) * 1000.0,
    )


def _payload_monotonic(value: Any) -> float | None:
    monotonic_value = getattr(value, "timestamp_monotonic", None)
    if isinstance(monotonic_value, int | float):
        return float(monotonic_value)
    monotonic_value = getattr(value, "monotonic_s", None)
    if isinstance(monotonic_value, int | float):
        return float(monotonic_value)
    timestamp_ms = getattr(value, "timestamp_ms", None)
    if isinstance(timestamp_ms, int | float):
        return float(timestamp_ms) / 1000.0
    return None


def instrument_input_stream(
    source: reactivex.Observable[Any],
    *,
    tap: InputDebugTap,
    stage: InputDebugStage,
    stream_name: str,
    source_id: SourceResolver,
    upstream_ids: Iterable[str] = (),
) -> reactivex.Observable[Any]:
    """Attach debug tap side effects to ``source`` without changing its payloads."""

    upstream_ids_tuple = tuple(upstream_ids)

    def _publish(value: Any) -> None:
        resolved_source = source_id(value) if callable(source_id) else source_id
        payload_monotonic = _payload_monotonic(value)
        if payload_monotonic is not None:
            tap.record_latency(stream_name, time.monotonic() - payload_monotonic)
        tap.publish(
            stage=stage,
            stream_name=stream_name,
            source_id=resolved_source,
            payload=value,
            upstream_ids=upstream_ids_tuple,
        )

    return pipe_in_background(source, ops.do_action(on_next=_publish))

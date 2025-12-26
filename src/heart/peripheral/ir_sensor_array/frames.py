"""Frame aggregation helpers for IR sample batches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .dma import IRSample


@dataclass(slots=True)
class IRFrame:
    """Collection of samples for a full frame across the sensor array."""

    frame_id: int
    samples: tuple[IRSample, ...]

    @property
    def arrival_times(self) -> list[float]:
        return [sample.timestamp for sample in self.samples]

    @property
    def payload_bits(self) -> list[int]:
        bits: list[int] = []
        for sample in self.samples:
            if sample.duration_us <= 0:
                continue
            # Assume the remote uses pulse-width modulation. Duration above
            # 1000 microseconds is treated as a logical "1".
            bits.append(1 if sample.duration_us >= 1000 else 0)
        return bits


class FrameAssembler:
    """Aggregate samples by ``frame_id`` until each sensor has contributed."""

    def __init__(self, *, sensor_count: int) -> None:
        if sensor_count <= 1:
            msg = "sensor_count must be greater than one"
            raise ValueError(msg)
        self.sensor_count = sensor_count
        self._pending: dict[int, dict[int, IRSample]] = {}

    def add(self, sample: IRSample) -> Iterator[IRFrame]:
        bucket = self._pending.setdefault(sample.frame_id, {})
        bucket[sample.sensor_index] = sample
        if len(bucket) < self.sensor_count:
            return iter(())

        frame_samples = tuple(
            bucket[index] for index in sorted(bucket)[: self.sensor_count]
        )
        del self._pending[sample.frame_id]
        return iter((IRFrame(frame_id=sample.frame_id, samples=frame_samples),))

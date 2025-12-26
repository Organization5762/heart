"""DMA-style packet buffering for IR sensor samples."""

from __future__ import annotations

import json
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

from .constants import DEFAULT_DMA_BUFFER_SIZE


@dataclass(slots=True)
class IRSample:
    """Single timestamped edge captured by a sensor in the array."""

    frame_id: int
    sensor_index: int
    timestamp: float
    level: int
    duration_us: float


@dataclass(slots=True)
class IRDMAPacket:
    """Chunk of captured IR samples transferred via DMA."""

    buffer_id: int
    samples: tuple[IRSample, ...]
    crc: int
    generated_at: datetime

    def to_bytes(self) -> bytes:
        payload = [
            {
                "frame_id": sample.frame_id,
                "sensor_index": sample.sensor_index,
                "timestamp": sample.timestamp,
                "level": sample.level,
                "duration_us": sample.duration_us,
            }
            for sample in self.samples
        ]
        return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def compute_crc(samples: Sequence[IRSample]) -> int:
    """Compute a simple checksum for IR samples."""

    crc = 0
    for sample in samples:
        crc ^= (sample.frame_id << 1) ^ (sample.sensor_index << 4)
        crc ^= int(sample.timestamp * 1_000_000)
        crc ^= sample.level << 8
        crc ^= int(sample.duration_us)
    return crc & 0xFFFFFFFF


class IRArrayDMAQueue:
    """Double-buffered queue that simulates a DMA capture pipeline."""

    def __init__(self, *, buffer_size: int = DEFAULT_DMA_BUFFER_SIZE) -> None:
        if buffer_size <= 0:
            msg = "buffer_size must be positive"
            raise ValueError(msg)
        self.buffer_size = buffer_size
        self._buffers: list[list[IRSample]] = [[], []]
        self._active = 0
        self._ready: deque[IRDMAPacket] = deque()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Producer API
    # ------------------------------------------------------------------
    def push_sample(self, sample: IRSample) -> None:
        """Append ``sample`` to the active DMA buffer."""

        with self._lock:
            buffer = self._buffers[self._active]
            buffer.append(sample)
            if len(buffer) >= self.buffer_size:
                self._finalize_active_buffer_locked()

    def flush(self) -> None:
        """Force the active buffer to be emitted even if not full."""

        with self._lock:
            if self._buffers[self._active]:
                self._finalize_active_buffer_locked()

    # ------------------------------------------------------------------
    # Consumer API
    # ------------------------------------------------------------------
    def pop(self) -> IRDMAPacket | None:
        """Return the next ready packet, if any."""

        with self._lock:
            if not self._ready:
                return None
            return self._ready.popleft()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _finalize_active_buffer_locked(self) -> None:
        buffer_id = self._active
        samples = tuple(self._buffers[buffer_id])
        self._buffers[buffer_id] = []
        self._active = 1 - self._active

        crc = compute_crc(samples)
        packet = IRDMAPacket(
            buffer_id=buffer_id,
            samples=samples,
            crc=crc,
            generated_at=datetime.now(timezone.utc),
        )
        self._ready.append(packet)

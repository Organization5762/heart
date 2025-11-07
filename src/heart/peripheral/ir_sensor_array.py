"""Infrared sensor array peripheral and positioning solver."""

from __future__ import annotations

import json
import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterator, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares

from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.event_bus import EventBus
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

SPEED_OF_LIGHT = 299_792_458.0  # metres per second


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


class IRArrayDMAQueue:
    """Double-buffered queue that simulates a DMA capture pipeline."""

    def __init__(self, *, buffer_size: int = 64) -> None:
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

        crc = self._crc_for_samples(samples)
        packet = IRDMAPacket(
            buffer_id=buffer_id,
            samples=samples,
            crc=crc,
            generated_at=datetime.now(timezone.utc),
        )
        self._ready.append(packet)

    @staticmethod
    def _crc_for_samples(samples: tuple[IRSample, ...]) -> int:
        crc = 0
        for sample in samples:
            crc ^= (sample.frame_id << 1) ^ (sample.sensor_index << 4)
            crc ^= int(sample.timestamp * 1_000_000)
            crc ^= sample.level << 8
            crc ^= int(sample.duration_us)
        return crc & 0xFFFFFFFF


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


class MultilaterationSolver:
    """Estimate the origin of an IR burst using time-difference-of-arrival."""

    def __init__(
        self,
        sensor_positions: Sequence[Sequence[float]],
        *,
        propagation_speed: float = SPEED_OF_LIGHT,
        max_iterations: int = 12,
        convergence_threshold: float = 1e-6,
    ) -> None:
        self.sensor_positions = np.asarray(sensor_positions, dtype=float)
        if self.sensor_positions.ndim != 2 or self.sensor_positions.shape[1] != 3:
            msg = "sensor_positions must be an (N,3) array"
            raise ValueError(msg)
        if self.sensor_positions.shape[0] < 3:
            msg = "At least three sensors are required"
            raise ValueError(msg)
        self.propagation_speed = float(propagation_speed)
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold

    # ------------------------------------------------------------------
    def solve(self, arrival_times: Sequence[float]) -> tuple[np.ndarray, float, float]:
        """Return ``(position, confidence, rmse)`` for ``arrival_times``."""

        times = np.asarray(arrival_times, dtype=float)
        if times.shape[0] != self.sensor_positions.shape[0]:
            msg = "arrival_times length must match number of sensors"
            raise ValueError(msg)

        point = np.mean(self.sensor_positions, axis=0)
        emission_time = float(np.min(times)) - np.linalg.norm(
            point - self.sensor_positions[0]
        ) / self.propagation_speed

        def objective(vector: np.ndarray) -> np.ndarray:
            candidate_point = vector[:3]
            candidate_emission = vector[3]
            residuals = []
            for sensor_pos, arrival in zip(
                self.sensor_positions, times, strict=True
            ):
                distance = np.linalg.norm(candidate_point - sensor_pos)
                residuals.append(
                    distance
                    - self.propagation_speed * (arrival - candidate_emission)
                )
            return np.asarray(residuals)

        start = np.concatenate([point, [emission_time]])
        result = least_squares(
            objective,
            start,
            method="trf",
            max_nfev=self.max_iterations * 100,
            xtol=self.convergence_threshold,
            ftol=self.convergence_threshold**2,
            gtol=self.convergence_threshold,
        )
        if not result.success:
            raise ValueError(f"Solver failed to converge: {result.message}")

        point = result.x[:3]
        emission_time = result.x[3]
        final_residuals = objective(result.x)

        rmse = float(math.sqrt(np.mean(np.square(final_residuals))))
        confidence = float(1.0 / (1.0 + rmse * self.propagation_speed))
        return point, confidence, rmse


class IRSensorArray(Peripheral):
    """Process DMA packets from an IR sensor array and emit pose estimates."""

    EVENT_FRAME = "peripheral.ir_array.frame"

    def __init__(
        self,
        *,
        sensor_positions: Sequence[Sequence[float]],
        event_bus: EventBus | None = None,
        propagation_speed: float = SPEED_OF_LIGHT,
    ) -> None:
        self._assembler = FrameAssembler(sensor_count=len(sensor_positions))
        self._solver = MultilaterationSolver(
            sensor_positions, propagation_speed=propagation_speed
        )
        self._calibration_offsets: dict[int, float] = {}
        self._event_bus = event_bus
        self._producer_id = id(self)
        super().__init__()

    # ------------------------------------------------------------------
    def attach_event_bus(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def apply_calibration(self, offsets: Mapping[int, float]) -> None:
        self._calibration_offsets = dict(offsets)

    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - integration hook for hardware
        logger.info("IRSensorArray run loop idle; use ingest_packet to feed data")

    # ------------------------------------------------------------------
    def ingest_packet(self, packet: IRDMAPacket) -> None:
        """Validate ``packet`` and emit pose events for complete frames."""

        expected_crc = IRArrayDMAQueue._crc_for_samples(packet.samples)
        if expected_crc != packet.crc:
            logger.warning(
                "Dropping packet due to CRC mismatch (expected=%s, got=%s)",
                expected_crc,
                packet.crc,
            )
            return

        for sample in packet.samples:
            for frame in self._assembler.add(sample):
                self._process_frame(frame, packet.generated_at)

    # ------------------------------------------------------------------
    def _process_frame(self, frame: IRFrame, generated_at: datetime) -> None:
        calibrated_times = []
        for sample in frame.samples:
            offset = self._calibration_offsets.get(sample.sensor_index, 0.0)
            calibrated_times.append(sample.timestamp - offset)

        position, confidence, rmse = self._solver.solve(calibrated_times)
        payload = {
            "frame_id": frame.frame_id,
            "bits": frame.payload_bits,
            "confidence": confidence,
            "rmse": rmse,
            "position": position.tolist(),
            "timestamp": generated_at.isoformat(),
        }

        if self._event_bus is not None:
            self._event_bus.emit(
                self.EVENT_FRAME,
                data=payload,
                producer_id=self._producer_id,
            )

        self.handle_input(
            Input(
                event_type=self.EVENT_FRAME,
                data=payload,
                producer_id=self._producer_id,
            )
        )


def radial_layout(radius: float = 0.12) -> list[list[float]]:
    """Return sensor positions for a square radial layout."""

    half = radius / math.sqrt(2)
    vertical = radius * 0.15
    return [
        [-half, 0.0, vertical],
        [0.0, half, -vertical],
        [half, 0.0, vertical],
        [0.0, -half, -vertical],
    ]


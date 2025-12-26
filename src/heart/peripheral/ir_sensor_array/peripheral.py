"""Peripheral implementation for the IR sensor array."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Sequence

from heart.peripheral.core import Input, Peripheral
from heart.utilities.logging import get_logger

from .constants import SPEED_OF_LIGHT
from .dma import IRDMAPacket, compute_crc
from .frames import FrameAssembler, IRFrame
from .solver import \
    DEFAULT_CONVERGENCE_THRESHOLD as SOLVER_DEFAULT_CONVERGENCE_THRESHOLD
from .solver import DEFAULT_MAX_ITERATIONS as SOLVER_DEFAULT_MAX_ITERATIONS
from .solver import DEFAULT_SOLVER_METHOD as SOLVER_DEFAULT_SOLVER_METHOD
from .solver import DEFAULT_USE_JACOBIAN as SOLVER_DEFAULT_USE_JACOBIAN
from .solver import MultilaterationSolver

logger = get_logger(__name__)

DEFAULT_SOLVER_METHOD = SOLVER_DEFAULT_SOLVER_METHOD
DEFAULT_MAX_ITERATIONS = SOLVER_DEFAULT_MAX_ITERATIONS
DEFAULT_CONVERGENCE_THRESHOLD = SOLVER_DEFAULT_CONVERGENCE_THRESHOLD
DEFAULT_USE_JACOBIAN = SOLVER_DEFAULT_USE_JACOBIAN


class IRSensorArray(Peripheral[Input]):
    """Process DMA packets from an IR sensor array and emit pose estimates."""

    EVENT_FRAME = "peripheral.ir_array.frame"

    def __init__(
        self,
        *,
        sensor_positions: Sequence[Sequence[float]],
        propagation_speed: float = SPEED_OF_LIGHT,
        solver_method: str = DEFAULT_SOLVER_METHOD,
        use_jacobian: bool = DEFAULT_USE_JACOBIAN,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        convergence_threshold: float = DEFAULT_CONVERGENCE_THRESHOLD,
    ) -> None:
        super().__init__()
        self._assembler = FrameAssembler(sensor_count=len(sensor_positions))
        self._solver = MultilaterationSolver(
            sensor_positions,
            propagation_speed=propagation_speed,
            solver_method=solver_method,
            use_jacobian=use_jacobian,
            max_iterations=max_iterations,
            convergence_threshold=convergence_threshold,
        )
        self._calibration_offsets: dict[int, float] = {}

    def apply_calibration(self, offsets: Mapping[int, float]) -> None:
        self._calibration_offsets = dict(offsets)

    # ------------------------------------------------------------------
    def ingest_packet(self, packet: IRDMAPacket) -> None:
        """Validate ``packet`` and emit pose events for complete frames."""

        expected_crc = compute_crc(packet.samples)
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

        self.handle_input(
            Input(
                event_type=self.EVENT_FRAME,
                data=payload,
            )
        )

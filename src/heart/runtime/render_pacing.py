from __future__ import annotations

import time
from dataclasses import dataclass

from heart.utilities.env.enums import RenderLoopPacingStrategy

DEFAULT_RENDER_LOOP_PACING_STRATEGY = RenderLoopPacingStrategy.OFF
DEFAULT_RENDER_LOOP_PACING_MIN_INTERVAL_MS = 0.0
DEFAULT_RENDER_LOOP_PACING_UTILIZATION_TARGET = 0.9


@dataclass(frozen=True)
class RenderLoopPacingConfig:
    strategy: RenderLoopPacingStrategy = DEFAULT_RENDER_LOOP_PACING_STRATEGY
    min_interval_ms: float = DEFAULT_RENDER_LOOP_PACING_MIN_INTERVAL_MS
    utilization_target: float = DEFAULT_RENDER_LOOP_PACING_UTILIZATION_TARGET


class RenderLoopPacer:
    def __init__(
        self,
        *,
        strategy: RenderLoopPacingStrategy = DEFAULT_RENDER_LOOP_PACING_STRATEGY,
        min_interval_ms: float = DEFAULT_RENDER_LOOP_PACING_MIN_INTERVAL_MS,
        utilization_target: float = DEFAULT_RENDER_LOOP_PACING_UTILIZATION_TARGET,
    ) -> None:
        self._strategy = strategy
        self._min_interval_ms = max(min_interval_ms, 0.0)
        self._utilization_target = self._validate_utilization(utilization_target)

    @staticmethod
    def _validate_utilization(utilization: float) -> float:
        if utilization <= 0.0 or utilization > 1.0:
            raise ValueError("Utilization target must be greater than 0 and at most 1")
        return utilization

    def pace(self, frame_start: float, estimated_cost_ms: float | None) -> float:
        if self._strategy == RenderLoopPacingStrategy.OFF:
            return 0.0
        target_interval_ms = self._min_interval_ms
        if estimated_cost_ms is not None:
            target_interval_ms = max(
                target_interval_ms,
                estimated_cost_ms / self._utilization_target,
            )
        target_interval_s = target_interval_ms / 1000.0
        elapsed_s = time.monotonic() - frame_start
        sleep_s = target_interval_s - elapsed_s
        if sleep_s > 0:
            time.sleep(sleep_s)
            return sleep_s
        return 0.0

from __future__ import annotations

import time

from heart.utilities.env import Configuration
from heart.utilities.env.enums import FramePacingStrategy


class FramePacer:
    def __init__(self, max_fps: int) -> None:
        self._max_fps = max_fps
        self._last_render_time: float | None = None

    def should_render(self, estimated_cost_ms: float | None) -> bool:
        if self._last_render_time is None:
            return True
        interval_s = self._target_interval_s(estimated_cost_ms)
        if interval_s <= 0.0:
            return True
        elapsed_s = time.monotonic() - self._last_render_time
        return elapsed_s >= interval_s

    def mark_rendered(self) -> None:
        self._last_render_time = time.monotonic()

    def _target_interval_s(self, estimated_cost_ms: float | None) -> float:
        interval_ms = self._base_interval_ms()
        interval_ms = max(interval_ms, Configuration.render_frame_min_interval_ms())
        if (
            Configuration.render_frame_pacing_strategy()
            == FramePacingStrategy.ADAPTIVE
            and estimated_cost_ms is not None
        ):
            interval_ms = max(interval_ms, self._adaptive_interval_ms(estimated_cost_ms))
        return interval_ms / 1000.0

    def _base_interval_ms(self) -> float:
        if self._max_fps <= 0:
            return 0.0
        return 1000.0 / self._max_fps

    @staticmethod
    def _adaptive_interval_ms(estimated_cost_ms: float) -> float:
        utilization = Configuration.render_frame_utilization_target()
        if utilization <= 0.0:
            return estimated_cost_ms
        return estimated_cost_ms / utilization

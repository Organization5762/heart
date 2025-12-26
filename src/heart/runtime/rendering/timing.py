from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from heart.utilities.env.enums import RendererTimingStrategy

DEFAULT_RENDERER_TIMING_EMA_ALPHA = 0.2
DEFAULT_RENDERER_TIMING_STRATEGY = RendererTimingStrategy.EMA


class _RendererLike(Protocol):
    name: str


@dataclass(frozen=True)
class RendererTimingSnapshot:
    name: str
    average_ms: float
    last_ms: float
    sample_count: int


@dataclass
class _RendererTimingState:
    average_ms: float = 0.0
    last_ms: float = 0.0
    sample_count: int = 0

    def record(
        self,
        duration_ms: float,
        *,
        strategy: RendererTimingStrategy,
        ema_alpha: float,
    ) -> None:
        self.sample_count += 1
        if self.sample_count == 1:
            self.average_ms = duration_ms
        elif strategy == RendererTimingStrategy.EMA:
            self.average_ms = (ema_alpha * duration_ms) + (
                (1.0 - ema_alpha) * self.average_ms
            )
        else:
            self.average_ms += (duration_ms - self.average_ms) / self.sample_count
        self.last_ms = duration_ms


class RendererTimingTracker:
    def __init__(
        self,
        *,
        strategy: RendererTimingStrategy = DEFAULT_RENDERER_TIMING_STRATEGY,
        ema_alpha: float = DEFAULT_RENDERER_TIMING_EMA_ALPHA,
    ) -> None:
        self._stats: dict[str, _RendererTimingState] = {}
        self._strategy = strategy
        self._ema_alpha = self._validate_ema_alpha(ema_alpha)

    @staticmethod
    def _validate_ema_alpha(alpha: float) -> float:
        if alpha <= 0.0 or alpha > 1.0:
            raise ValueError("EMA alpha must be greater than 0 and at most 1")
        return alpha

    def record(self, renderer_name: str, duration_ms: float) -> None:
        state = self._stats.get(renderer_name)
        if state is None:
            state = _RendererTimingState()
            self._stats[renderer_name] = state
        state.record(
            duration_ms,
            strategy=self._strategy,
            ema_alpha=self._ema_alpha,
        )

    def estimate_total_ms(self, renderers: Iterable[_RendererLike]) -> tuple[float, bool]:
        total_ms = 0.0
        has_samples = False
        for renderer in renderers:
            state = self._stats.get(renderer.name)
            if state is None:
                continue
            total_ms += state.average_ms
            has_samples = True
        return total_ms, has_samples

    def snapshot(
        self, renderers: Iterable[_RendererLike]
    ) -> tuple[list[RendererTimingSnapshot], list[str]]:
        snapshots: list[RendererTimingSnapshot] = []
        missing: list[str] = []
        for renderer in renderers:
            state = self._stats.get(renderer.name)
            if state is None:
                missing.append(renderer.name)
                continue
            snapshots.append(
                RendererTimingSnapshot(
                    name=renderer.name,
                    average_ms=state.average_ms,
                    last_ms=state.last_ms,
                    sample_count=state.sample_count,
                )
            )
        return snapshots, missing

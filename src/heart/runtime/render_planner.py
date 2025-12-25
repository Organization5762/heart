from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from heart.runtime.rendering.timing import (RendererTimingSnapshot,
                                            RendererTimingTracker)
from heart.runtime.rendering.variants import RendererVariant
from heart.utilities.env import Configuration
from heart.utilities.env.enums import RenderMergeStrategy
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer

logger = get_logger(__name__)
log_controller = get_logging_controller()


@dataclass(frozen=True)
class RenderPlan:
    variant: RendererVariant
    merge_strategy: RenderMergeStrategy
    estimated_cost_ms: float
    has_samples: bool
    timing_snapshots: list[RendererTimingSnapshot]
    timing_missing: list[str]


class RenderPlanner:
    def __init__(
        self, timing_tracker: RendererTimingTracker, default_variant: RendererVariant
    ) -> None:
        self._timing_tracker = timing_tracker
        self._default_variant = default_variant
        self._current_merge_strategy = Configuration.render_merge_strategy()

    def get_merge_strategy(self) -> RenderMergeStrategy:
        return self._current_merge_strategy

    def set_default_variant(self, default_variant: RendererVariant) -> None:
        self._default_variant = default_variant

    def plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderPlan:
        variant = self.resolve_variant(renderers, override_renderer_variant)
        merge_strategy = self._resolve_merge_strategy(renderers)
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        snapshots, missing = self._timing_tracker.snapshot(renderers)
        self._current_merge_strategy = merge_strategy
        plan = RenderPlan(
            variant=variant,
            merge_strategy=merge_strategy,
            estimated_cost_ms=estimated_cost_ms,
            has_samples=has_samples,
            timing_snapshots=snapshots,
            timing_missing=missing,
        )
        self._log_render_plan(plan, len(renderers))
        return plan

    def resolve_variant(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RendererVariant:
        return self._resolve_render_variant(renderers, override_renderer_variant)

    def _resolve_merge_strategy(
        self, renderers: list["StatefulBaseRenderer[Any]"]
    ) -> RenderMergeStrategy:
        configured = Configuration.render_merge_strategy()
        if configured != RenderMergeStrategy.ADAPTIVE:
            return configured
        surface_threshold = Configuration.render_merge_surface_threshold()
        if len(renderers) < surface_threshold:
            return RenderMergeStrategy.IN_PLACE
        cost_threshold_ms = Configuration.render_merge_cost_threshold_ms()
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        if cost_threshold_ms == 0:
            return RenderMergeStrategy.BATCHED
        if has_samples and estimated_cost_ms >= cost_threshold_ms:
            return RenderMergeStrategy.BATCHED
        return RenderMergeStrategy.IN_PLACE

    def _resolve_render_variant(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RendererVariant:
        variant = override_renderer_variant or self._default_variant
        if variant == RendererVariant.AUTO:
            threshold = Configuration.render_parallel_threshold()
            if len(renderers) < threshold:
                return RendererVariant.ITERATIVE
            cost_threshold_ms = Configuration.render_parallel_cost_threshold_ms()
            estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
                renderers
            )
            if cost_threshold_ms == 0:
                return RendererVariant.BINARY
            if has_samples and estimated_cost_ms >= cost_threshold_ms:
                return RendererVariant.BINARY
            return RendererVariant.ITERATIVE
        return variant

    def _log_render_plan(self, plan: RenderPlan, renderer_count: int) -> None:
        snapshot_payload = [
            {
                "renderer": snapshot.name,
                "average_ms": snapshot.average_ms,
                "last_ms": snapshot.last_ms,
                "samples": snapshot.sample_count,
            }
            for snapshot in plan.timing_snapshots
        ]
        log_message = (
            "render.plan variant=%s merge_strategy=%s renderer_count=%s "
            "estimated_cost_ms=%.2f has_samples=%s"
        )
        log_args = (
            plan.variant.name,
            plan.merge_strategy.value,
            renderer_count,
            plan.estimated_cost_ms,
            plan.has_samples,
        )
        log_extra = {
            "variant": plan.variant.name,
            "merge_strategy": plan.merge_strategy.value,
            "renderer_count": renderer_count,
            "estimated_cost_ms": plan.estimated_cost_ms,
            "has_samples": plan.has_samples,
            "renderer_timings": snapshot_payload,
            "renderer_timings_missing": plan.timing_missing,
        }

        log_controller.log(
            key="render.plan",
            logger=logger,
            level=logging.INFO,
            msg=log_message,
            args=log_args,
            extra=log_extra,
            fallback_level=logging.DEBUG,
        )

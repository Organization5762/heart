from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from heart.runtime.rendering.timing import RendererTimingTracker
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


class RenderPlanner:
    def __init__(
        self, timing_tracker: RendererTimingTracker, default_variant: RendererVariant
    ) -> None:
        self._timing_tracker = timing_tracker
        self._default_variant = default_variant
        self._current_merge_strategy = Configuration.render_merge_strategy()

    def get_merge_strategy(self) -> RenderMergeStrategy:
        return self._current_merge_strategy

    def plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        override_renderer_variant: RendererVariant | None,
    ) -> RenderPlan:
        variant = self._resolve_render_variant(renderers, override_renderer_variant)
        self._current_merge_strategy = self._resolve_merge_strategy(renderers)
        self._log_render_plan(renderers, variant)
        return RenderPlan(variant=variant, merge_strategy=self._current_merge_strategy)

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

    def _log_render_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        variant: RendererVariant,
    ) -> None:
        estimated_cost_ms, has_samples = self._timing_tracker.estimate_total_ms(
            renderers
        )
        snapshots, missing = self._timing_tracker.snapshot(renderers)
        snapshot_payload = [
            {
                "renderer": snapshot.name,
                "average_ms": snapshot.average_ms,
                "last_ms": snapshot.last_ms,
                "samples": snapshot.sample_count,
            }
            for snapshot in snapshots
        ]
        log_message = (
            "render.plan variant=%s merge_strategy=%s renderer_count=%s "
            "estimated_cost_ms=%.2f has_samples=%s"
        )
        log_args = (
            variant.name,
            self._current_merge_strategy.value,
            len(renderers),
            estimated_cost_ms,
            has_samples,
        )
        log_extra = {
            "variant": variant.name,
            "merge_strategy": self._current_merge_strategy.value,
            "renderer_count": len(renderers),
            "estimated_cost_ms": estimated_cost_ms,
            "has_samples": has_samples,
            "renderer_timings": snapshot_payload,
            "renderer_timings_missing": missing,
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

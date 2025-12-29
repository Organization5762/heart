from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from heart.runtime.rendering.plan import RenderPlan, RenderPlanner
from heart.runtime.rendering.variants import RendererVariant
from heart.utilities.env.enums import RenderPlanSignatureStrategy

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


class RenderPlanCache:
    def __init__(
        self,
        planner: RenderPlanner,
        refresh_ms: int,
        signature_strategy: RenderPlanSignatureStrategy,
    ) -> None:
        self._planner = planner
        self._refresh_ms = refresh_ms
        self._signature_strategy = signature_strategy
        self._signature: tuple[int, ...] | None = None
        self._override: RendererVariant | None = None
        self._default_variant: RendererVariant | None = None
        self._plan_time = 0.0
        self._plan: RenderPlan | None = None
        self._timing_version: int | None = None

    def get_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        default_variant: RendererVariant,
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        signature = self._renderers_signature(renderers, self._signature_strategy)
        timing_version = self._planner.timing_version()
        if self._is_cache_valid(
            signature,
            override_renderer_variant,
            default_variant,
            timing_version,
        ):
            return cast(RenderPlan, self._plan)
        self._planner.set_default_variant(default_variant)
        plan = self._planner.plan(renderers, override_renderer_variant)
        self._signature = signature
        self._override = override_renderer_variant
        self._default_variant = default_variant
        self._plan_time = time.monotonic()
        self._plan = plan
        self._timing_version = timing_version
        return plan

    def _is_cache_valid(
        self,
        signature: tuple[int, ...],
        override_renderer_variant: RendererVariant | None,
        default_variant: RendererVariant,
        timing_version: int,
    ) -> bool:
        if self._refresh_ms <= 0 or self._plan is None:
            return False
        if signature != self._signature or override_renderer_variant != self._override:
            return False
        if default_variant != self._default_variant:
            return False
        if timing_version != self._timing_version:
            return False
        age_ms = (time.monotonic() - self._plan_time) * 1000.0
        return age_ms < self._refresh_ms

    @staticmethod
    def _renderers_signature(
        renderers: list["StatefulBaseRenderer[Any]"],
        signature_strategy: RenderPlanSignatureStrategy,
    ) -> tuple[int, ...]:
        if signature_strategy == RenderPlanSignatureStrategy.TYPE:
            return tuple(id(type(renderer)) for renderer in renderers)
        return tuple(id(renderer) for renderer in renderers)

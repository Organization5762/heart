from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from heart.runtime.render_planner import RenderPlan, RenderPlanner
from heart.runtime.rendering.variants import RendererVariant
from heart.utilities.env.enums import RenderPlanRefreshStrategy

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


class RenderPlanCache:
    def __init__(
        self,
        planner: RenderPlanner,
        refresh_ms: int,
        refresh_strategy: RenderPlanRefreshStrategy,
    ) -> None:
        self._planner = planner
        self._refresh_ms = refresh_ms
        self._refresh_strategy = refresh_strategy
        self._signature: tuple[int, ...] | None = None
        self._override: RendererVariant | None = None
        self._default_variant: RendererVariant | None = None
        self._plan_time = 0.0
        self._plan: RenderPlan | None = None

    def get_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        default_variant: RendererVariant,
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        signature = self._renderers_signature(renderers)
        if self._is_cache_valid(
            signature,
            override_renderer_variant,
            default_variant,
        ):
            return cast(RenderPlan, self._plan)
        self._planner.set_default_variant(default_variant)
        plan = self._planner.plan(renderers, override_renderer_variant)
        self._signature = signature
        self._override = override_renderer_variant
        self._default_variant = default_variant
        self._plan_time = time.monotonic()
        self._plan = plan
        return plan

    def _is_cache_valid(
        self,
        signature: tuple[int, ...],
        override_renderer_variant: RendererVariant | None,
        default_variant: RendererVariant,
    ) -> bool:
        if self._plan is None:
            return False
        if signature != self._signature or override_renderer_variant != self._override:
            return False
        if default_variant != self._default_variant:
            return False
        if self._refresh_strategy == RenderPlanRefreshStrategy.ON_CHANGE:
            return True
        if self._refresh_ms <= 0:
            return False
        age_ms = (time.monotonic() - self._plan_time) * 1000.0
        return age_ms < self._refresh_ms

    @staticmethod
    def _renderers_signature(
        renderers: list["StatefulBaseRenderer[Any]"],
    ) -> tuple[int, ...]:
        return tuple(id(renderer) for renderer in renderers)

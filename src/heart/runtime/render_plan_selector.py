from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

from heart.runtime.render_plan_cache import RenderPlanCache
from heart.runtime.render_planner import RenderPlan, RenderPlanner
from heart.runtime.rendering.variants import RendererVariant, RenderMethod
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.renderers import StatefulBaseRenderer


class RenderPlanSelector:
    def __init__(
        self,
        planner: RenderPlanner,
        render_dispatch: dict[RendererVariant, RenderMethod],
    ) -> None:
        self._planner = planner
        self._render_dispatch = render_dispatch
        self._active_plan: RenderPlan | None = None
        self._plan_cache = RenderPlanCache(
            planner,
            Configuration.render_plan_refresh_ms(),
            Configuration.render_plan_signature_strategy(),
        )

    def get_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        render_variant: RendererVariant,
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        return self._plan_cache.get_plan(
            renderers,
            render_variant,
            override_renderer_variant,
        )

    def get_active_plan(
        self,
        renderers: list["StatefulBaseRenderer[Any]"],
        render_variant: RendererVariant,
        override_renderer_variant: RendererVariant | None = None,
    ) -> RenderPlan:
        if self._active_plan is not None:
            return self._active_plan
        return self.get_plan(renderers, render_variant, override_renderer_variant)

    def resolve_render_method(self, plan: RenderPlan) -> RenderMethod:
        return self._render_dispatch.get(
            plan.variant,
            self._render_dispatch[RendererVariant.ITERATIVE],
        )

    @contextmanager
    def activate_plan(self, plan: RenderPlan) -> Generator[None, None, None]:
        self._active_plan = plan
        try:
            yield
        finally:
            self._active_plan = None

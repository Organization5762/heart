from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererResolver(Protocol):
    def resolve(self, dependency: type[RendererT]) -> RendererT:
        """Resolve renderer instances from the shared container."""


def resolve_renderer_spec(
    renderer: RendererSpec,
    resolver: RendererResolver | None,
    *,
    context: str,
) -> StatefulBaseRenderer:
    if isinstance(renderer, type):
        if not issubclass(renderer, StatefulBaseRenderer):
            raise TypeError(f"{context} requires StatefulBaseRenderer subclasses")
        if resolver is None:
            raise ValueError(f"{context} requires a renderer resolver")
        return resolver.resolve(renderer)
    return renderer


def resolve_renderer_specs(
    renderers: Iterable[RendererSpec],
    resolver: RendererResolver | None,
    *,
    context: str,
) -> list[StatefulBaseRenderer]:
    return [
        resolve_renderer_spec(renderer, resolver, context=context)
        for renderer in renderers
    ]

from __future__ import annotations

from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererResolver(Protocol):
    def resolve(self, dependency: type[RendererT]) -> RendererT:
        """Resolve renderer instances from the shared container."""


def resolve_renderer_spec(
    renderer: RendererSpec,
    renderer_resolver: RendererResolver | None,
    owner: str,
) -> StatefulBaseRenderer:
    if isinstance(renderer, type):
        if not issubclass(renderer, StatefulBaseRenderer):
            raise TypeError(f"{owner} requires StatefulBaseRenderer subclasses")
        if renderer_resolver is None:
            raise ValueError(f"{owner} requires a renderer resolver")
        return renderer_resolver.resolve(renderer)
    return renderer

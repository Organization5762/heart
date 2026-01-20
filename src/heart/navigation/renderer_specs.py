from __future__ import annotations

from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererResolver(Protocol):
    def resolve(self, dependency: type[RendererT]) -> RendererT:
        """Resolve renderer instances from the shared container."""


class RendererFactory(Protocol[RendererT]):
    def __call__(self) -> RendererT:
        """Instantiate a renderer."""


def resolve_renderer_spec(
    renderer: RendererSpec,
    resolver: RendererResolver | None = None,
) -> StatefulBaseRenderer:
    if isinstance(renderer, type):
        if not issubclass(renderer, StatefulBaseRenderer):
            raise TypeError("Requires StatefulBaseRenderer subclasses")
        if resolver is None:
            raise ValueError("renderer resolver is required for class specs")
        return resolver.resolve(renderer)
    return renderer

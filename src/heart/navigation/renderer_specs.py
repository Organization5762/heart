from __future__ import annotations

from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer
from heart.runtime.container import container

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererResolver(Protocol):
    def resolve(self, dependency: type[RendererT]) -> RendererT:
        """Resolve renderer instances from the shared container."""


def resolve_renderer_spec(
    renderer: RendererSpec,
) -> StatefulBaseRenderer:
    if isinstance(renderer, type):
        if not issubclass(renderer, StatefulBaseRenderer):
            raise TypeError("Requires StatefulBaseRenderer subclasses")
        return container.resolve(renderer)
    return renderer

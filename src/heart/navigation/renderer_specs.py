from __future__ import annotations

from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererFactory(Protocol[RendererT]):
    def __call__(self) -> RendererT:
        """Instantiate a renderer."""


class RendererResolver(Protocol):
    def resolve(self, renderer: type[RendererT]) -> RendererT:
        """Resolve a renderer type into an instance."""


def resolve_renderer_spec(
    renderer: RendererSpec,
    resolver: RendererResolver | None = None,
) -> StatefulBaseRenderer:
    if isinstance(renderer, StatefulBaseRenderer):
        return renderer
    if resolver is None:
        msg = (
            "Renderer types require a renderer resolver. "
            "Pass an instance or provide a resolver."
        )
        raise ValueError(msg)
    return resolver.resolve(renderer)

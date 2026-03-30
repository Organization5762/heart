from __future__ import annotations

from typing import Protocol, TypeVar

from heart.renderers import StatefulBaseRenderer

RendererT = TypeVar("RendererT", bound=StatefulBaseRenderer)
RendererSpec = StatefulBaseRenderer | type[StatefulBaseRenderer]


class RendererFactory(Protocol[RendererT]):
    def __call__(self) -> RendererT:
        """Instantiate a renderer."""


class RendererResolver(Protocol):
    def resolve(self, renderer_type: type[RendererT]) -> RendererT:
        """Resolve ``renderer_type`` to an initialized renderer instance."""


def resolve_renderer_spec(
    renderer: RendererSpec,
    resolver: RendererResolver | None = None,
) -> StatefulBaseRenderer:
    if isinstance(renderer, StatefulBaseRenderer):
        return renderer
    if isinstance(renderer, type) and issubclass(renderer, StatefulBaseRenderer):
        if resolver is None:
            raise ValueError("A renderer resolver is required for renderer types.")
        return resolver.resolve(renderer)
    raise TypeError(f"Unsupported renderer spec: {renderer!r}")

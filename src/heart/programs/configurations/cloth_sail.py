"""Configuration for the farmhouse-nautical cloth renderer."""

from heart.renderers.cloth_sail import ClothSailRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("cloth_sail")
    mode.resolve_renderer(loop.context_container, ClothSailRenderer)

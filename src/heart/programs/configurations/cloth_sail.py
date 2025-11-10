"""Configuration for the farmhouse-nautical cloth renderer."""

from heart.display.renderers.cloth_sail import ClothSailRenderer
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("cloth_sail")
    mode.add_renderer(ClothSailRenderer())

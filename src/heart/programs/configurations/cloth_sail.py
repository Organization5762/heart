"""Configuration for the farmhouse-nautical cloth renderer."""

from heart.environment import GameLoop
from heart.renderers.cloth_sail import (ClothSailRenderer,
                                        ClothSailStateProvider)


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("cloth_sail")
    mode.add_renderer(
        ClothSailRenderer(
            builder=ClothSailStateProvider(loop.peripheral_manager)
        )
    )

"""Configuration wiring for the PixelSunriseRenderer demo."""

from heart.display.renderers.pixel_sunrise import PixelSunriseRenderer
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    """Register a single mode that runs the PixelSunriseRenderer."""

    mode = loop.add_mode("Pixel Sunrise Demo")
    mode.add_renderer(PixelSunriseRenderer())

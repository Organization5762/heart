"""Configuration for the brass porthole window renderer."""

from heart.display.renderers.porthole_window import PortholeWindowRenderer
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("porthole_window")
    mode.add_renderer(PortholeWindowRenderer())

"""Configuration for the brass porthole window renderer."""

from heart.renderers.porthole_window import PortholeWindowRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("porthole_window")
    mode.add_renderer(PortholeWindowRenderer)

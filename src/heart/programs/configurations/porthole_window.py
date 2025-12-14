"""Configuration for the brass porthole window renderer."""

from heart.environment import GameLoop
from heart.renderers.porthole_window import (PortholeWindowRenderer,
                                             PortholeWindowStateProvider)


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("porthole_window")
    mode.add_renderer(
        PortholeWindowRenderer(
            builder=loop.context_container.resolve(PortholeWindowStateProvider)
        )
    )

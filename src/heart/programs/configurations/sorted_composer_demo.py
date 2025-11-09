from heart.display.color import Color
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop
from heart.navigation import (SortedComposedRenderer,
                              switch_controlled_renderer_order)


def configure(loop: GameLoop) -> None:
    """Showcase sorting a composed stack with the rotary switch."""

    mode = loop.add_mode("Switch sorted stack")

    layered_text = [
        TextRendering(
            text=["Layer A"],
            font="Roboto",
            font_size=24,
            color=Color(255, 90, 90),
            y_location=22,
        ),
        TextRendering(
            text=["Layer B"],
            font="Roboto",
            font_size=24,
            color=Color(90, 255, 120),
            y_location=22,
        ),
        TextRendering(
            text=["Layer C"],
            font="Roboto",
            font_size=24,
            color=Color(120, 135, 255),
            y_location=22,
        ),
    ]

    mode.add_renderer(
        SortedComposedRenderer(layered_text, sorter=switch_controlled_renderer_order)
    )

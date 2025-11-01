import pytest

from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop


def test_creating_(loop: GameLoop) -> None:
    # Now we get automatic movement between A and B, facilitated by AppController
    a = loop.add_mode("A")
    b = loop.add_mode("B")

    # But what is GameMode actually doing here? It is just a builder for a thing that does nothing?
    a.add_renderer(
        RenderColor(Color(255, 0, 0)),
        RenderColor(Color(0, 255, 0)),
        RenderColor(Color(0, 0, 255)),
    )

    b.add_renderer(
        RenderColor(Color(255, 255, 0)),
        RenderColor(Color(0, 255, 255)),
        RenderColor(Color(255, 0, 255)),
    )


if __name__ == "__main__":
    pytest.main()

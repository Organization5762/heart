import pytest

from heart.display.color import Color
from heart.renderers.color import RenderColor
from heart.runtime.game_loop import GameLoop


class TestNavigationNavigation:
    """Group Navigation Navigation tests so navigation navigation behaviour stays reliable. This preserves confidence in navigation navigation for end-to-end scenarios."""

    def test_creating_(self, loop: GameLoop) -> None:
        # Now we get automatic movement between A and B, facilitated by AppController
        """Verify that a GameLoop can create modes and attach renderers without errors. This guards the core loop contract so demos can spin up basic scenes reliably."""
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

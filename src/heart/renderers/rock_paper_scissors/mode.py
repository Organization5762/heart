from heart.display.color import Color
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.text import TextRendering
from heart.runtime.game_loop import GameLoop

from .renderer import RockPaperScissorsRenderer
from .title import RockPaperScissorsTitle


def add_rock_paper_scissors_mode(
    loop: GameLoop,
    *,
    randomness: RandomnessProvider,
) -> None:
    """Register the rock-paper-scissors mode on a game loop."""

    mode = loop.add_mode(
        loop.compose(
            [
                RockPaperScissorsTitle(randomness=randomness),
                TextRendering(
                    text=["Shi Fu Mi"],
                    font="Grand9K Pixel.ttf",
                    font_size=14,
                    color=Color(255, 255, 255),
                    y_location=0.7,
                ),
            ]
        )
    )
    mode.add_renderer(RockPaperScissorsRenderer(randomness=randomness))

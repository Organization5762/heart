from heart.display.color import Color
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.pacman import PacmanGhostRenderer
from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    randomness = RandomnessProvider()
    mode = loop.add_mode()
    mode.add_renderer(
        RandomPixel(
            color=Color(187, 10, 30),
            num_pixels=50,
            randomness=randomness,
        )
    )
    mode.resolve_renderer_from_container(PacmanGhostRenderer)
    mode.add_renderer(Border(width=2, color=Color(187, 10, 30)))

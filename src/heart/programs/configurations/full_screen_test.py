from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    randomness = RandomnessProvider()
    mode = loop.add_mode("pixel")
    mode.add_renderer(RandomPixel(num_pixels=200, randomness=randomness))
    mode.add_renderer(Border(width=2))

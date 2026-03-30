from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.pixels import Border
from heart.renderers.random_pixel import RandomPixel
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    randomness = RandomnessProvider()
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(num_pixels=40000, brightness=0.05, randomness=randomness))
    mode.add_renderer(RandomPixel(num_pixels=4000, brightness=0.10, randomness=randomness))
    mode.add_renderer(RandomPixel(num_pixels=400, brightness=0.25, randomness=randomness))
    mode.add_renderer(RandomPixel(num_pixels=40, brightness=0.50, randomness=randomness))
    mode.add_renderer(RandomPixel(num_pixels=4, brightness=1, randomness=randomness))
    mode.add_renderer(Border(width=2))

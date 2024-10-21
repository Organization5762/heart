from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    height = 64
    width = 512
    mode.add_renderer(MandelbrotMode(width, height))
    # for _ in range(0, 50):
    #     mode.add_renderer(RandomPixel())
    # mode.add_renderer(Border(width=2))

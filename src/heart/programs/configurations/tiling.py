from heart.display.renderers import tiling
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(tiling.PythagoreanTiling())
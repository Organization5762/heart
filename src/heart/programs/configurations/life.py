from heart.display.renderers.life import Life
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(Life())

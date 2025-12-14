from heart.display.color import Color
from heart.environment import GameLoop
from heart.renderers.color import RenderColor


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RenderColor(color=Color(155, 155, 155)))

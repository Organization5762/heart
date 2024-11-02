from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RenderColor(color=Color(155, 155, 155)))

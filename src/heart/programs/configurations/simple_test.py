from heart.display.color import Color
from heart.renderers.color import RenderColor
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(RenderColor(color=Color(155, 155, 155)))

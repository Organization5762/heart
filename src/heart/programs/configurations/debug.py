from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:

    a = loop.add_scene()
    a.scenes.append(RenderColor(Color(255, 0, 0)))
    a.scenes.append(RenderColor(Color(0, 255, 0)))
    a.scenes.append(RenderColor(Color(0, 0, 255)))

    b = loop.add_mode()

    b.add_renderer(
        RenderColor(Color(255, 255, 0)),
        RenderColor(Color(0, 255, 255)),
        RenderColor(Color(255, 0, 255)),
    )

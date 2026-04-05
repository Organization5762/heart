from heart.display.color import Color
from heart.renderers.color import RenderColor
from heart.renderers.rubiks_connected_x_debug import \
    RubiksConnectedXDebugRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("rubiks x debug")
    mode.add_renderer(RenderColor(Color(0, 0, 0)))
    mode.add_renderer(RubiksConnectedXDebugRenderer())

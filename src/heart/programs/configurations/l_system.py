from heart.renderers.l_system import LSystem
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.resolve_renderer_from_container(LSystem)

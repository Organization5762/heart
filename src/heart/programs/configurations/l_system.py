from heart.display.renderers.l_system import LSystem, LSystemStateProvider
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(
        LSystem(builder=loop.context_container.resolve(LSystemStateProvider))
    )

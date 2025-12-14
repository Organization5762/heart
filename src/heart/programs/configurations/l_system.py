from heart.environment import GameLoop
from heart.renderers.l_system import LSystem, LSystemStateProvider


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(
        LSystem(builder=loop.context_container.resolve(LSystemStateProvider))
    )

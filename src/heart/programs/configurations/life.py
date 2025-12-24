from heart.environment import GameLoop
from heart.renderers.modules.life.renderer import Life


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.resolve_renderer(container=loop, renderer=Life)

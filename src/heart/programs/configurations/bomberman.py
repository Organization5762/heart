from heart.renderers.bomberman import BombermanRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode(title="Bomberman")
    mode.add_renderer(BombermanRenderer)

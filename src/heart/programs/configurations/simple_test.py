from heart.renderers.kirby import KirbyScene
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    kirby_mode = loop.add_mode(KirbyScene.title_scene())
    kirby_mode.resolve_renderer_from_container(KirbyScene)

from heart.renderers.vibe import VibeScene
from heart.runtime.game_loop import GameLoop

from .lib_2025 import configure as configure_lib_2025


def configure(loop: GameLoop) -> None:
    vibe_mode = loop.add_mode(VibeScene.title_scene())
    vibe_mode.add_renderer(VibeScene)

    configure_lib_2025(loop)

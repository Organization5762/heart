from heart.renderers.water_cube.renderer import WaterCube
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("water")
    mode.resolve_renderer(container=loop.context_container, renderer=WaterCube)

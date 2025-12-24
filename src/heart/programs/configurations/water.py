from heart.environment import GameLoop
from heart.renderers.modules.water_cube.renderer import WaterCube


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("water")
    mode.resolve_renderer(container=loop.context_container, renderer=WaterCube)

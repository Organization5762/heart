from heart.display.color import Color
from heart.renderers.cube_pong.renderer import CubePongRenderer
from heart.renderers.text import TextRendering
from heart.runtime.game_loop import GameLoop


def add_cube_pong_mode(loop: GameLoop) -> None:
    mode = loop.add_mode(
        TextRendering(
            text=["cube\npong"],
            font="Grand9K Pixel.ttf",
            font_size=12,
            color=Color(255, 105, 180),
            y_location=15 / 64,
            line_spacing_px=-2,
        )
    )
    mode.add_renderer(CubePongRenderer())

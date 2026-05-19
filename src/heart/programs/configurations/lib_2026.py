from typing import Callable

import numpy as np

from heart.display.color import Color
from heart.navigation import MultiScene
from heart.peripheral.providers.randomness import RandomnessProvider
from heart.renderers.hilbert_curve import HilbertScene
from heart.renderers.image import RenderImage
from heart.renderers.kirby import KirbyScene
from heart.renderers.life.renderer import Life
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbrot.title import MandelbrotTitle
from heart.renderers.mario.renderer import MarioRenderer
from heart.renderers.multicolor import MulticolorRenderer
from heart.renderers.palette_tunnel import PaletteTunnelScene
from heart.renderers.pranay_sketch import PranaySketchRenderer
from heart.renderers.rock_paper_scissors import add_rock_paper_scissors_mode
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.spritesheet_random import SpritesheetLoopRandom
from heart.renderers.text import TextRendering
from heart.renderers.three_fractal import FractalScene
from heart.renderers.tixyland import Tixyland, TixylandFactory
from heart.renderers.water_cube.renderer import WaterCube
from heart.renderers.water_title_screen import WaterTitleScreen
from heart.runtime.game_loop import GameLoop

TITLE_TILE_HEIGHT_PX = 64
TITLE_FONT_SIZE = 14
TITLE_LINE_HEIGHT_PX = 21
TITLE_LINE_SPACING_PX = -4
PRANAY_SKETCH_MODE_TITLE = "Dolly's\nsketch"


def pattern_numpy(t: float, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    t_i = int(t)
    val = (Y - 2 * t_i) * (X - 2 - t_i)
    return val


def centered_text_title(text: str) -> TextRendering:
    return centered_text(
        text=text,
        font_size=TITLE_FONT_SIZE,
        color=Color(255, 255, 255),
        line_height_px=TITLE_LINE_HEIGHT_PX,
        line_spacing_px=TITLE_LINE_SPACING_PX,
    )


def centered_text(
    *,
    text: str,
    font_size: int,
    color: Color,
    line_height_px: int,
    line_spacing_px: int = 0,
) -> TextRendering:
    lines = text.splitlines()
    block_height = len(lines) * line_height_px
    if len(lines) > 1:
        block_height += (len(lines) - 1) * line_spacing_px
    y_location = (TITLE_TILE_HEIGHT_PX - block_height) / 2 / TITLE_TILE_HEIGHT_PX
    return TextRendering(
        text=[text],
        font="Grand9K Pixel.ttf",
        font_size=font_size,
        color=color,
        y_location=y_location,
        line_spacing_px=line_spacing_px,
    )


def friend_beacon_text(text: str) -> TextRendering:
    return centered_text(
        text=text,
        font_size=12,
        color=Color(255, 105, 180),
        line_height_px=18,
        line_spacing_px=-2,
    )


def configure(loop: GameLoop) -> None:
    randomness = RandomnessProvider()
    kirby_mode = loop.add_mode(KirbyScene.title_scene())
    kirby_mode.add_renderer(KirbyScene)

    modelbrot = loop.add_mode(
        title=loop.compose(
            [
                MandelbrotTitle(),
                TextRendering(
                    text=["mandelbrot"],
                    font="Grand9K Pixel.ttf",
                    font_size=14,
                    color=Color(255, 255, 255),
                    y_location=0.55,
                ),
            ]
        )
    )
    modelbrot.add_renderer(MandelbrotMode)

    sphere_mode = loop.add_mode(centered_text_title("3d\nfractal"))
    sphere_mode.add_renderer(FractalScene)

    palette_tunnel_mode = loop.add_mode(centered_text_title("palette\ntunnel"))
    palette_tunnel_mode.add_renderer(PaletteTunnelScene())

    hilbert_mode = loop.add_mode(centered_text_title("hilbert"))
    hilbert_mode.add_renderer(HilbertScene)

    mario_mode = loop.add_mode(
        loop.compose(
            [
                RenderImage(image_file="mario_still.png"),
                TextRendering(
                    text=["mario"],
                    font="Grand9K Pixel.ttf",
                    font_size=14,
                    color=Color(255, 0, 0),
                    y_location=0.05,
                ),
            ]
        )
    )
    mario_mode.add_renderer(MarioRenderer)

    add_rock_paper_scissors_mode(loop, randomness=randomness)

    def multicolor_renderer() -> MulticolorRenderer:
        return loop.resolve(MulticolorRenderer)

    shroomed_mode = loop.add_mode(
        loop.compose(
            [
                multicolor_renderer(),
                TextRendering(
                    text=["shroomed"],
                    font="Grand9K Pixel.ttf",
                    font_size=11,
                    color=Color(0, 0, 0),
                    y_location=0.5,
                ),
            ]
        )
    )
    shroomed_mode.add_renderer(
        loop.compose(
            [
                multicolor_renderer(),
                SpritesheetLoop(
                    sheet_file_path="ness.png", metadata_file_path="ness.json"
                ),
            ]
        )
    )

    water_mode = loop.add_mode(
        loop.compose(
            [
                loop.resolve(WaterTitleScreen),
                TextRendering(
                    text=["water"],
                    font="Grand9K Pixel.ttf",
                    font_size=14,
                    color=Color(255, 105, 180),
                    y_location=0.5,
                ),
            ]
        )
    )
    water_mode.add_renderer(WaterCube)

    pranay_mode = loop.add_mode(friend_beacon_text(text=PRANAY_SKETCH_MODE_TITLE))
    pranay_mode.add_renderer(PranaySketchRenderer())

    friend_beacon_mode = loop.add_mode(friend_beacon_text(text="friend\nbeacon"))
    friend_beacon_mode.add_renderer(
        MultiScene(
            [
                *[
                    friend_beacon_text(text=f"Where's\n{name}")
                    for name in [
                        "seb",
                        "cal",
                        "clem",
                        "michaēl",
                        "james",
                        "eric",
                        "macy",
                        "faye",
                        "big W",
                        "mel",
                        "stu",
                        "elena",
                        "steve",
                        "jill",
                        "graham",
                        "sam",
                        "matt",
                        "sri",
                        "sue anna",
                        "pranay",
                        "amir",
                        "victor",
                        "connor",
                        "david",
                        "penny",
                        "nicole",
                        "greg",
                        "brody",
                    ]
                ],
                friend_beacon_text(text="Lost my\nfriends\nagain"),
            ]
        )
    )

    tixyland = loop.add_mode("tixyland")
    tixyland_factory = loop.resolve(TixylandFactory)

    def build_tixyland(
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray],
    ) -> Tixyland:
        return tixyland_factory(fn)

    tixyland.add_renderer(
        MultiScene(
            [
                build_tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                build_tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape) < 0.1),
                build_tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape)),
                build_tixyland(fn=lambda t, i, x, y: np.sin(np.ones(x.shape) * t)),
                build_tixyland(fn=lambda t, i, x, y: y - t * t),
                build_tixyland(
                    fn=lambda t, i, x, y: np.sin(
                        t
                        - np.sqrt((x - x.shape[0] / 2) ** 2 + (y - y.shape[1] / 2) ** 2)
                    )
                ),
                build_tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                build_tixyland(fn=lambda t, i, x, y: pattern_numpy(t, x, y)),
            ]
        )
    )

    life = loop.add_mode("life")
    life.add_renderer(Life)

    spooky = loop.add_mode("spook")
    spooky.add_renderer(
        SpritesheetLoopRandom(
            screen_width=64,
            screen_height=64,
            screen_count=4,
            sheet_file_path="spookyeye.png",
            metadata_file_path="spookyeye.json",
            randomness=randomness,
        )
    )

from typing import Callable

import numpy as np

from heart.display.color import Color
from heart.navigation import MultiScene
from heart.renderers.artist import ArtistScene
from heart.renderers.combined_bpm_screen import CombinedBpmScreen
from heart.renderers.heart_title_screen import HeartTitleScreen
from heart.renderers.hilbert_curve import HilbertScene
from heart.renderers.image import RenderImage
from heart.renderers.kirby import KirbyScene
from heart.renderers.life.renderer import Life
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbrot.title import MandelbrotTitle
from heart.renderers.mario.renderer import MarioRenderer
from heart.renderers.multicolor import MulticolorRenderer
from heart.renderers.random_pixel import RandomPixel
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.spritesheet_random import SpritesheetLoopRandom
from heart.renderers.text import TextRendering
from heart.renderers.three_fractal import FractalScene
from heart.renderers.tixyland import Tixyland, TixylandFactory
from heart.renderers.water_cube.renderer import WaterCube
from heart.renderers.water_title_screen import WaterTitleScreen
from heart.runtime.game_loop import GameLoop


def pattern_numpy(t: float, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    t_i = int(t)
    val = (Y - 2 * t_i) * (X - 2 - t_i)
    return val


def configure(loop: GameLoop) -> None:
    kirby_mode = loop.add_mode(KirbyScene.title_scene())
    kirby_mode.resolve_renderer_from_container(KirbyScene)

    modelbrot = loop.add_mode(
        loop.compose(
            [
                MandelbrotTitle(),
                TextRendering(
                    text=["mandelbrot"],
                    font="Roboto",
                    font_size=14,
                    color=Color(255, 255, 255),
                    y_location=35,
                ),
            ]
        )
    )
    modelbrot.resolve_renderer_from_container(MandelbrotMode)

    sphere_mode = loop.add_mode("3d fractal")
    sphere_mode.resolve_renderer_from_container(FractalScene)

    hilbert_mode = loop.add_mode("hilbert")
    hilbert_mode.resolve_renderer_from_container(HilbertScene)

    mario_mode = loop.add_mode(
        loop.compose(
            [
                RenderImage(image_file="mario_still.png"),
                TextRendering(
                    text=["mario"],
                    font="Roboto",
                    font_size=14,
                    color=Color(255, 0, 0),
                    y_location=5,
                ),
            ]
        )
    )
    mario_mode.resolve_renderer_from_container(MarioRenderer)

    def multicolor_renderer() -> MulticolorRenderer:
        return loop.resolve(MulticolorRenderer)

    shroomed_mode = loop.add_mode(
        loop.compose(
            [
                multicolor_renderer(),
                TextRendering(
                    text=["shroomed"],
                    font="Roboto",
                    font_size=14,
                    color=Color(0, 0, 0),
                    y_location=32,
                ),
            ]
        )
    )
    shroomed_mode.add_renderer(
        loop.compose(
            [
                multicolor_renderer(),
                SpritesheetLoop("ness.png", "ness.json"),
            ]
        )
    )

    heart_rate_mode = loop.add_mode(
        loop.compose(
            [
                loop.resolve(HeartTitleScreen),
                TextRendering(
                    text=["heart rate"],
                    font="Roboto",
                    font_size=14,
                    color=Color(255, 105, 180),
                    y_location=32,
                ),
            ]
        )
    )
    heart_rate_mode.resolve_renderer_from_container(CombinedBpmScreen)

    water_mode = loop.add_mode(
        loop.compose(
            [
                loop.resolve(WaterTitleScreen),
                TextRendering(
                    text=["water"],
                    font="Roboto",
                    font_size=14,
                    color=Color(255, 105, 180),
                    y_location=32,
                ),
            ]
        )
    )

    water_mode.resolve_renderer_from_container(WaterCube)

    artist_mode = loop.add_mode(ArtistScene.title_scene())
    artist_mode.resolve_renderer_from_container(ArtistScene)

    friend_beacon_mode = loop.add_mode("friend\nbeacon")
    friend_beacon_mode.add_renderer(
        MultiScene(
            [
                *[
                    TextRendering.default(text=f"Where's\n{name}")
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
                TextRendering.default(text="Lost my\nfriends\nagain"),
            ]
        )
    )

    # Some random ones
    tixyland = loop.add_mode("tixyland")
    tixyland_factory = loop.resolve(TixylandFactory)

    def build_tixyland(
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
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
    life.resolve_renderer_from_container(Life)

    spooky = loop.add_mode("spook")
    spooky.add_renderer(
        SpritesheetLoopRandom(
            screen_width=64,
            screen_height=64,
            screen_count=4,
            sheet_file_path="spookyeye.png",
            metadata_file_path="spookyeye.json",
        )
    )

    confetti = loop.add_mode("confetti")
    confetti.add_renderer(
        loop.compose(
            [
                RandomPixel(num_pixels=40000, brightness=0.05),
                RandomPixel(num_pixels=4000, brightness=0.10),
                RandomPixel(num_pixels=2000, brightness=0.25),
                RandomPixel(num_pixels=500, brightness=0.50),
                RandomPixel(num_pixels=50, brightness=1),
            ]
        )
    )

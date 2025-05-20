import numpy as np

from heart.display.color import Color
from heart.display.renderers.artist import ArtistScene
from heart.display.renderers.combined_bpm_screen import CombinedBpmScreen
from heart.display.renderers.free_text import FreeTextRenderer
from heart.display.renderers.heart_title_screen import HeartTitleScreen
from heart.display.renderers.hilbert_curve import HilbertScene
from heart.display.renderers.image import RenderImage
from heart.display.renderers.kirby import KirbyScene
from heart.display.renderers.life import Life
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.display.renderers.mandelbrot.title import MandelbrotTitle
from heart.display.renderers.mario import MarioRenderer
from heart.display.renderers.multicolor import MulticolorRenderer
from heart.display.renderers.pixels import Border, RandomPixel
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.spritesheet_random import SpritesheetLoopRandom
from heart.display.renderers.text import TextRendering
from heart.display.renderers.three_fractal import FractalScene
from heart.display.renderers.tixyland import Tixyland
from heart.display.renderers.water_cube import WaterCube
from heart.display.renderers.water_title_screen import WaterTitleScreen
from heart.display.renderers.yolisten import YoListenRenderer
from heart.environment import GameLoop
from heart.navigation import ComposedRenderer, MultiScene


def pattern_numpy(t: float, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    t_i = int(t)
    val = (Y - 2 * t_i) * (X - 2 - t_i)
    return val


def configure(loop: GameLoop) -> None:
    free_text_mode = loop.add_mode("free text")
    free_text_mode.add_renderer(FreeTextRenderer())

    kirby_mode = loop.add_mode(KirbyScene.title_scene())
    kirby_mode.add_renderer(KirbyScene())

    modelbrot = loop.add_mode(
        ComposedRenderer(
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
    modelbrot.add_renderer(MandelbrotMode())

    sphere_mode = loop.add_mode("3d fractal")
    sphere_mode.add_renderer(FractalScene(loop.device))

    hilbert_mode = loop.add_mode("hilbert")
    hilbert_mode.add_renderer(HilbertScene())

    mario_mode = loop.add_mode(
        ComposedRenderer(
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
    mario_mode.add_renderer(
        MarioRenderer(
            sheet_file_path=f"mario_64.png",
            metadata_file_path=f"mario_64.json",
        )
    )

    shroomed_mode = loop.add_mode(
        ComposedRenderer(
            [
                MulticolorRenderer(),
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
        ComposedRenderer(
            [
                MulticolorRenderer(),
                SpritesheetLoop("ness.png", "ness.json"),
            ]
        )
    )

    heart_rate_mode = loop.add_mode(
        ComposedRenderer(
            [
                HeartTitleScreen(),
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
    heart_rate_mode.add_renderer(CombinedBpmScreen())

    water_mode = loop.add_mode(
        ComposedRenderer(
            [
                WaterTitleScreen(),
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
    water_mode.add_renderer(WaterCube())

    artist_mode = loop.add_mode(ArtistScene.title_scene())
    artist_mode.add_renderer(ArtistScene())

    mode = loop.add_mode("friend\nbeacon")

    # TODO: Refactor
    text = ["Lost my\nfriends\nagain"]
    text.extend(
        [
            f"Where's\n{name}"
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
                "amir",
                "sue anna",
                "brody",
            ]
        ]
    )
    text.append("Where is\neveryone")
    mode.add_renderer(
        TextRendering(
            font="Comic Sans MS", font_size=14, color=Color(255, 105, 180), text=text
        )
    )

    # Some random ones
    tixyland = loop.add_mode(
        TextRendering(
            text=["tixyland"],
            font="Roboto",
            font_size=14,
            color=Color(255, 105, 180),
            y_location=32,
        )
    )
    tixyland.add_renderer(
        MultiScene(
            [
                Tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                Tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape) < 0.1),
                Tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape)),
                Tixyland(fn=lambda t, i, x, y: np.sin(np.ones(x.shape) * t)),
                Tixyland(fn=lambda t, i, x, y: y - t * t),
                Tixyland(
                    fn=lambda t, i, x, y: np.sin(
                        t
                        - np.sqrt((x - x.shape[0] / 2) ** 2 + (y - y.shape[1] / 2) ** 2)
                    )
                ),
                Tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                Tixyland(fn=lambda t, i, x, y: pattern_numpy(t, x, y)),
            ]
        )
    )

    life = loop.add_mode("life")
    life.add_renderer(Life())

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
        ComposedRenderer(
            [
                RandomPixel(num_pixels=40000, brightness=0.05),
                RandomPixel(num_pixels=4000, brightness=0.10),
                RandomPixel(num_pixels=2000, brightness=0.25),
                RandomPixel(num_pixels=500, brightness=0.50),
                RandomPixel(num_pixels=50, brightness=1),
            ]
        )
    )

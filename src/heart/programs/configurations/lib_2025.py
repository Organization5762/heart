from heart.display.color import Color
from heart.display.renderers.hilbert_curve import HilbertScene
from heart.display.renderers.image import RenderImage
from heart.display.renderers.kirby import KirbyScene
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.display.renderers.mandelbrot.title import MandelbrotTitle
from heart.display.renderers.mario import MarioRenderer
from heart.display.renderers.multicolor import MulticolorRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.display.renderers.three_fractal import FractalScene
from heart.display.renderers.yolisten import YoListenRenderer
from heart.display.renderers.combined_bpm_screen import CombinedBpmScreen
from heart.display.renderers.water_cube import WaterCube
from heart.display.renderers.heart_title_screen import HeartTitleScreen
from heart.display.renderers.water_title_screen import WaterTitleScreen
from heart.environment import GameLoop
from heart.navigation import ComposedRenderer


def configure(loop: GameLoop) -> None:
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

    yolisten_mode = loop.add_mode("yo listen")
    yolisten_mode.add_renderer(YoListenRenderer())

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

    shroomed_mode = loop.add_mode("shroomed")
    shroomed_mode.add_renderer(MulticolorRenderer())
    shroomed_mode.add_renderer(SpritesheetLoop("ness.png", "ness.json"))

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

    mode = loop.add_mode("friend beacon")

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
                "eric",
                "faye",
                "big W",
                "spriha",
                "andrew",
                "mel",
                "stu",
                "elena",
                "jill",
                "graham",
                "russell",
                "sam",
                "sri",
            ]
        ]
    )
    text.append("Where is\neveryone")
    mode.add_renderer(
        TextRendering(
            font="Comic Sans MS", font_size=20, color=Color(255, 105, 180), text=text
        )
    )

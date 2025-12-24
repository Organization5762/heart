from heart.display.color import Color
from heart.navigation import ComposedRenderer, MultiScene
from heart.renderers.hilbert_curve import HilbertScene
from heart.renderers.kirby import KirbyScene
from heart.renderers.mandelbrot.scene import MandelbrotMode
from heart.renderers.mandelbrot.title import MandelbrotTitle
from heart.renderers.text import TextRendering
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    kirby_mode = loop.add_mode(KirbyScene.title_scene())
    kirby_mode.resolve_renderer(loop.context_container, KirbyScene)

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
    modelbrot.resolve_renderer(loop.context_container, MandelbrotMode)

    hilbert_mode = loop.add_mode("hilbert")
    hilbert_mode.resolve_renderer(loop.context_container, HilbertScene)

    mode = loop.add_mode("friend\nbeacon")
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
        MultiScene(
            scenes=[
                TextRendering(
                    font="Comic Sans MS",
                    font_size=20,
                    color=Color(255, 105, 180),
                    text=text,
                ),
                TextRendering(
                    font="Comic Sans MS",
                    font_size=20,
                    color=Color(255, 105, 180),
                    text=text,
                ),
                TextRendering(
                    font="Comic Sans MS",
                    font_size=20,
                    color=Color(255, 105, 180),
                    text=text,
                ),
            ]
        )
    )

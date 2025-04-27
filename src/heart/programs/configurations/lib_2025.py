from heart.display.color import Color
from heart.display.renderers.hilbert_curve import HilbertScene
from heart.display.renderers.kirby import KirbyScene
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.display.renderers.text import TextRendering
from heart.display.renderers.yolisten import YoListenRenderer
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:

    kirby_mode = loop.add_mode("kirby mode")
    kirby_mode.add_renderer(KirbyScene())
    kirby_mode.add_title_renderer(*KirbyScene.title_scene())

    modelbrot = loop.add_mode("mandelbrot")
    modelbrot.add_renderer(MandelbrotMode())

    hilbert_mode = loop.add_mode("hilbert")
    hilbert_mode.add_renderer(HilbertScene())

    yolisten_mode = loop.add_mode("yo listen")
    yolisten_mode.add_renderer(YoListenRenderer())

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

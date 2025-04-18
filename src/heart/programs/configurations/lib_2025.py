from heart.display.color import Color
from heart.display.renderers.hilbert_curve import HilbertScene
from heart.display.renderers.mandelbrot.scene import MandelbrotMode
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    width = 64
    height = 64

    # TODO: There's some desire to refactor this into one "column" and then use the
    # button to iterate through
    mode = loop.add_mode()
    for kirby in [
        "kirby_flying_32",
        "kirby_cell_64",
        "kirby_sleep_64",
        "tornado_kirby",
        "swimming_kirby",
        "running_kirby",
        "rolling_kirby",
        "fighting_kirby",
    ]:
        mode = loop.add_mode()
        mode.add_renderer(
            SpritesheetLoop(
                screen_width=width,
                screen_height=height,
                sheet_file_path=f"{kirby}.png",
                metadata_file_path=f"{kirby}.json",
            )
        )

    modelbrot = loop.add_mode()
    modelbrot.add_renderer(MandelbrotMode())

    hilbert_mode = loop.add_mode()
    hilbert_mode.add_renderer(HilbertScene())

    mode = loop.add_mode()

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

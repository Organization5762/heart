from heart.display.color import Color
from heart.display.renderers.life import Life
from heart.display.renderers.mandelbrot import MandelbrotMode
from heart.display.renderers.pacman import PacmanGhostRenderer
from heart.display.renderers.pixels import Border, RandomPixel
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.spritesheet_random import SpritesheetLoopRandom
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    width = 64
    height = 64

    # KIRBY
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
    # PacMan
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(color=Color(187, 10, 30), num_pixels=50))
    mode.add_renderer(PacmanGhostRenderer())
    mode.add_renderer(Border(width=2, color=Color(187, 10, 30)))

    # SpookyEye
    mode = loop.add_mode()
    width = 64
    height = 64
    screen_count = 8
    mode.add_renderer(
        SpritesheetLoopRandom(
            screen_width=width,
            screen_height=height,
            screen_count=screen_count,
            sheet_file_path="spookyeye.png",
            metadata_file_path="spookyeye.json",
        )
    )

    # Confetti
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(num_pixels=200))
    mode.add_renderer(Border(width=2))

    # Game of Life
    mode = loop.add_mode()
    mode.add_renderer(Life())

    mode = loop.add_mode()
    # MANDELBROT
    mode.add_renderer(MandelbrotMode())

    width = 64
    height = 64

    # KIRBY
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
    # PacMan
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(color=Color(187, 10, 30), num_pixels=50))
    mode.add_renderer(PacmanGhostRenderer())
    mode.add_renderer(Border(width=2, color=Color(187, 10, 30)))

    # SpookyEye
    mode = loop.add_mode()
    width = 64
    height = 64
    screen_count = 8
    mode.add_renderer(
        SpritesheetLoopRandom(
            screen_width=width,
            screen_height=height,
            screen_count=screen_count,
            sheet_file_path="spookyeye.png",
            metadata_file_path="spookyeye.json",
        )
    )

    # Confetti
    mode = loop.add_mode()
    mode.add_renderer(RandomPixel(num_pixels=40000, brightness=0.05))
    mode.add_renderer(RandomPixel(num_pixels=4000, brightness=0.10))
    mode.add_renderer(RandomPixel(num_pixels=400, brightness=0.25))
    mode.add_renderer(RandomPixel(num_pixels=40, brightness=0.50))
    mode.add_renderer(RandomPixel(num_pixels=4, brightness=1))
    mode.add_renderer(Border(width=2))

    # Game of Life
    mode = loop.add_mode()
    mode.add_renderer(Life())

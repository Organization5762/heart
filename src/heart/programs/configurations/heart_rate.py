from heart.environment import GameLoop
from heart.renderers.max_bpm_screen import MaxBpmScreen


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("heart_rate")

    mode.add_renderer(MaxBpmScreen())
    # mode.add_renderer(MetadataScreen())

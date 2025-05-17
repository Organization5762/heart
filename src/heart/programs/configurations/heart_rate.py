from heart.display.renderers.max_bpm_screen import MaxBpmScreen
from heart.display.renderers.metadata_screen import MetadataScreen
from heart.environment import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("heart_rate")

    mode.add_renderer(MaxBpmScreen())
    # mode.add_renderer(MetadataScreen())

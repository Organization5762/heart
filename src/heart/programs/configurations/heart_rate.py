from heart.environment import GameLoop
from heart.renderers.max_bpm_screen import MaxBpmScreen


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("heart_rate")

    mode.resolve_renderer(loop.context_container, MaxBpmScreen)
    # mode.add_renderer(MetadataScreen())

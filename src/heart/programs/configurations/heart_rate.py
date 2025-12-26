from heart.renderers.max_bpm_screen import MaxBpmScreen
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("heart_rate")

    mode.resolve_renderer_from_container(MaxBpmScreen)
    # mode.add_renderer(MetadataScreen())

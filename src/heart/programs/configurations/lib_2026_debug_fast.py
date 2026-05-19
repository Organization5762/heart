import os

from heart.programs.configurations.lib_2026_debug_cycle import \
    configure as configure_debug_cycle
from heart.runtime.game_loop import GameLoop

DEFAULT_TOTEM_DEBUG_FAST_SECONDS = "1"


def configure(loop: GameLoop) -> None:
    os.environ.setdefault(
        "HEART_TOTEM_DEBUG_CYCLE_SECONDS",
        DEFAULT_TOTEM_DEBUG_FAST_SECONDS,
    )
    configure_debug_cycle(loop)

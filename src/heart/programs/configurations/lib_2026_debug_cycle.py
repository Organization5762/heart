import os

from heart.navigation.debug_cycle import TotemDebugCycle
from heart.programs.configurations.lib_2026 import \
    configure as configure_lib_2026
from heart.runtime.game_loop import GameLoop

DEFAULT_TOTEM_DEBUG_CYCLE_SECONDS = 5.0


def configure(loop: GameLoop) -> None:
    configure_lib_2026(loop)
    post_processors = loop.components.game_modes.state.post_processors
    if not post_processors:
        post_processors.extend(loop.components.game_modes._default_post_processors())
    post_processors.append(
        TotemDebugCycle(
            loop.components.game_modes,
            interval_seconds=_debug_cycle_seconds(),
            start_mode=_debug_start_mode(),
        )
    )


def _debug_cycle_seconds() -> float:
    raw_value = os.environ.get(
        "HEART_TOTEM_DEBUG_CYCLE_SECONDS",
        str(DEFAULT_TOTEM_DEBUG_CYCLE_SECONDS),
    )
    try:
        return float(raw_value)
    except ValueError:
        return DEFAULT_TOTEM_DEBUG_CYCLE_SECONDS


def _debug_start_mode() -> str | None:
    return os.environ.get("HEART_TOTEM_DEBUG_START_MODE")

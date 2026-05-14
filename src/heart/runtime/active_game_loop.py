from __future__ import annotations

from typing import Any

_ACTIVE_GAME_LOOP: Any | None = None


def get_active_game_loop() -> Any | None:
    return _ACTIVE_GAME_LOOP


def set_active_game_loop(loop: Any) -> None:
    global _ACTIVE_GAME_LOOP
    _ACTIVE_GAME_LOOP = loop

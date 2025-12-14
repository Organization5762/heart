from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PacmanGhostState:
    screen_width: int
    screen_height: int
    last_corner: str | None = None
    blood: bool = True
    reverse: bool = False
    x: int = 0
    y: int = 0
    pacman_idx: int = 0
    switch_pacman: bool = True
    asset_version: int = 0

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class RockPaperScissorsPhase(StrEnum):
    INTRO = "intro"
    COUNTDOWN = "countdown"
    REVEAL = "reveal"


@dataclass(frozen=True, slots=True)
class RockPaperScissorsState:
    phase: RockPaperScissorsPhase
    phase_started_at: float
    selected_throw: str

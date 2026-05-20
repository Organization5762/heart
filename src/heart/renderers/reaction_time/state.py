from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReactionPhase(StrEnum):
    IDENTIFY = "identify"
    COUNTDOWN = "countdown"
    WAIT = "wait"
    GO = "go"
    RESULTS = "results"


@dataclass(frozen=True, slots=True)
class ReactionPlayerState:
    reaction_time_s: float | None = None
    false_start: bool = False


@dataclass(frozen=True, slots=True)
class ReactionTimeState:
    phase: ReactionPhase
    phase_started_at: float
    go_at: float
    players: tuple[ReactionPlayerState, ...]
    round_number: int = 1


def new_reaction_round(
    *,
    now: float,
    player_count: int,
    round_number: int,
) -> ReactionTimeState:
    return ReactionTimeState(
        phase=ReactionPhase.IDENTIFY,
        phase_started_at=now,
        go_at=0.0,
        players=tuple(ReactionPlayerState() for _ in range(player_count)),
        round_number=round_number,
    )


def reaction_winner(players: tuple[ReactionPlayerState, ...]) -> int | None:
    best_index: int | None = None
    best_time: float | None = None
    for index, player in enumerate(players):
        if player.false_start or player.reaction_time_s is None:
            continue
        if best_time is None or player.reaction_time_s < best_time:
            best_time = player.reaction_time_s
            best_index = index
    return best_index

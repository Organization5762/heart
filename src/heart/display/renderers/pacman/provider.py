from __future__ import annotations

import random

import pygame

from heart.display.renderers.pacman.state import PacmanGhostState


class PacmanGhostStateProvider:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self._asset_version = 0

    def initial_state(self, window: pygame.Surface) -> PacmanGhostState:
        width, height = window.get_size()
        return self._spawn_state(width=width, height=height, blood=True)

    def next_state(self, state: PacmanGhostState) -> PacmanGhostState:
        delta = -5 if state.reverse else 5
        new_x = state.x + delta
        next_switch = not state.switch_pacman
        next_pacman_idx = (state.pacman_idx + 1) % 3 if state.switch_pacman else state.pacman_idx

        if new_x > state.screen_width + 50 or new_x < -150:
            return self._spawn_state(
                width=state.screen_width,
                height=state.screen_height,
                blood=not state.blood,
                pacman_idx=next_pacman_idx,
                switch_pacman=next_switch,
            )

        return PacmanGhostState(
            screen_width=state.screen_width,
            screen_height=state.screen_height,
            last_corner=state.last_corner,
            blood=state.blood,
            reverse=state.reverse,
            x=new_x,
            y=state.y,
            pacman_idx=next_pacman_idx,
            switch_pacman=next_switch,
            asset_version=state.asset_version,
        )

    def _spawn_state(
        self,
        *,
        width: int,
        height: int,
        blood: bool,
        pacman_idx: int = 0,
        switch_pacman: bool = True,
    ) -> PacmanGhostState:
        corner = self._rng.choice(["top_left", "top_right", "bottom_left", "bottom_right"])
        if corner == "top_left":
            x = -50
            y = 16
            reverse = False
        elif corner == "top_right":
            x = width + 50
            y = 16
            reverse = True
        elif corner == "bottom_left":
            x = -50
            y = height - 48
            reverse = False
        else:
            x = width + 50
            y = height - 48
            reverse = True

        self._asset_version += 1
        return PacmanGhostState(
            screen_width=width,
            screen_height=height,
            last_corner=corner,
            blood=blood,
            reverse=reverse,
            x=x,
            y=y,
            pacman_idx=pacman_idx,
            switch_pacman=switch_pacman,
            asset_version=self._asset_version,
        )

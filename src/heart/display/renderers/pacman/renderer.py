from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.assets.loader import Loader
from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer
from heart.display.renderers.pacman.provider import PacmanGhostStateProvider
from heart.display.renderers.pacman.state import PacmanGhostState
from heart.peripheral.core.manager import PeripheralManager


class PacmanGhostRenderer(AtomicBaseRenderer[PacmanGhostState]):
    def __init__(self, builder: PacmanGhostStateProvider | None = None) -> None:
        self._builder = builder or PacmanGhostStateProvider()
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.ghost1: pygame.Surface | None = None
        self.ghost2: pygame.Surface | None = None
        self.ghost3: pygame.Surface | None = None
        self.pacman: pygame.Surface | None = None
        self._asset_version: int = 0

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> PacmanGhostState:
        initial_state = self._builder.initial_state(window)
        self._asset_version = initial_state.asset_version
        self._load_sprites(initial_state)
        return initial_state

    def _load_sprites(self, state: PacmanGhostState) -> None:
        load = Loader.load
        ghost_prefix = "scaredghost" if state.blood else "pinkghost"
        ghost_blue = "blueghost.png"
        ghost_red = "redghost.png"

        if state.reverse:
            self.ghost1 = pygame.transform.flip(load("scaredghost1.png" if state.blood else ghost_prefix + ".png"), True, False)
            self.ghost2 = pygame.transform.flip(load(ghost_blue if not state.blood else "scaredghost2.png"), True, False)
            self.ghost3 = pygame.transform.flip(load("scaredghost1.png" if state.blood else ghost_red), True, False)
        else:
            self.ghost1 = load("scaredghost1.png" if state.blood else ghost_prefix + ".png")
            self.ghost2 = load("scaredghost2.png" if state.blood else ghost_blue)
            self.ghost3 = load("scaredghost1.png" if state.blood else ghost_red)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        next_state = self._builder.next_state(self.state)
        if next_state.asset_version != self._asset_version:
            self._asset_version = next_state.asset_version
            self._load_sprites(next_state)
        self.set_state(next_state)
        state = self.state

        pacman = Loader.load(
            f"bloodpac{state.pacman_idx + 1}.png" if state.blood else f"pac{state.pacman_idx + 1}.png"
        )
        if (state.reverse and not state.blood) or (state.blood and not state.reverse):
            pacman = pygame.transform.flip(pacman, True, False)

        x = state.x
        y = state.y
        if (not state.blood and state.reverse) or (state.blood and not state.reverse):
            window.blit(pacman, (x, y))
            if self.ghost1 and self.ghost2 and self.ghost3:
                window.blit(self.ghost1, (x + 32, y))
                window.blit(self.ghost2, (x + 64, y))
                window.blit(self.ghost3, (x + 96, y))
        if state.blood and state.reverse or (not state.blood and not state.reverse):
            if self.ghost1 and self.ghost2 and self.ghost3:
                window.blit(self.ghost3, (x, y))
                window.blit(self.ghost2, (x + 32, y))
                window.blit(self.ghost1, (x + 64, y))
            window.blit(pacman, (x + 96, y))

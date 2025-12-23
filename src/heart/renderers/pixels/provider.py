import random
from dataclasses import replace

import pygame
import reactivex
from reactivex import operators as ops

from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.pixels.state import BorderState, RainState, SlinkyState


class BorderStateProvider:
    def __init__(self, initial_color: Color | None = None) -> None:
        self._initial_color = initial_color or Color.random()

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> BorderState:
        return BorderState(color=self._initial_color)

    def update_color(self, state: BorderState, color: Color) -> BorderState:
        return replace(state, color=color)


class RainStateProvider(ObservableProvider[RainState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        peripheral_manager: PeripheralManager,
        rng: random.Random | None = None,
    ) -> None:
        self._width = width
        self._height = height
        self._peripheral_manager = peripheral_manager
        self._rng = rng or random.Random()

    def observable(self) -> reactivex.Observable[RainState]:
        initial_state = self._initial_state()
        return self._peripheral_manager.game_tick.pipe(
            ops.scan(self._advance_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _initial_state(self) -> RainState:
        initial_y = self._rng.randint(0, 20)
        return RainState(
            self._rng.randint(0, self._width),
            current_y=initial_y,
        )

    def _advance_state(self, state: RainState, _: object) -> RainState:
        new_y = state.current_y + 1
        if new_y > self._height:
            return replace(
                state,
                starting_point=self._rng.randint(0, self._width),
            )
        return replace(state, current_y=new_y)


class SlinkyStateProvider(ObservableProvider[SlinkyState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        peripheral_manager: PeripheralManager,
        rng: random.Random | None = None,
    ) -> None:
        self._width = width
        self._height = height
        self._peripheral_manager = peripheral_manager
        self._rng = rng or random.Random()

    def observable(self) -> reactivex.Observable[SlinkyState]:
        initial_state = self._initial_state()
        return self._peripheral_manager.game_tick.pipe(
            ops.scan(self._advance_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _initial_state(self) -> SlinkyState:
        return SlinkyState(
            starting_point=self._rng.randint(0, self._width),
            current_y=self._rng.randint(0, 20),
        )

    def _advance_state(self, state: SlinkyState, _: object) -> SlinkyState:
        new_y = state.current_y + 1
        if new_y > self._height:
            return replace(
                state,
                starting_point=self._rng.randint(0, self._width),
            )
        return replace(state, current_y=new_y)

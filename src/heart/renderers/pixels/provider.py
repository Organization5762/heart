from __future__ import annotations

import random
from dataclasses import replace

import reactivex
from reactivex import operators as ops
from reactivex.subject import BehaviorSubject

from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.pixels.state import BorderState, RainState, SlinkyState
from heart.renderers.state_provider import RngStateProvider
from heart.utilities.reactivex_threads import pipe_in_background


class BorderStateProvider(ObservableProvider[BorderState]):
    def __init__(self, initial_color: Color | None = None) -> None:
        self._color = BehaviorSubject(initial_color or Color.random())

    def observable(self) -> reactivex.Observable[BorderState]:
        return pipe_in_background(
            self._color,
            ops.map(lambda color: BorderState(color=color)),
            ops.share(),
        )

    def set_color(self, color: Color) -> None:
        self._color.on_next(color)


class RainStateProvider(RngStateProvider[RainState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        peripheral_manager: PeripheralManager,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(rng=rng)
        self._width = width
        self._height = height
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[RainState]:
        initial_state = RainState(
            starting_point=self.rng.randint(0, self._width),
            current_y=self.rng.randint(0, 20),
        )

        return pipe_in_background(
            self._peripheral_manager.game_tick,
            ops.scan(lambda state, _: self._next_state(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _next_state(self, state: RainState) -> RainState:
        new_y = state.current_y + 1
        if new_y > self._height:
            return replace(
                state,
                starting_point=self.rng.randint(0, self._width),
                current_y=0,
            )
        return replace(state, current_y=new_y)


class SlinkyStateProvider(RngStateProvider[SlinkyState]):
    def __init__(
        self,
        *,
        width: int,
        height: int,
        peripheral_manager: PeripheralManager,
        rng: random.Random | None = None,
    ) -> None:
        super().__init__(rng=rng)
        self._width = width
        self._height = height
        self._peripheral_manager = peripheral_manager

    def observable(self) -> reactivex.Observable[SlinkyState]:
        initial_state = SlinkyState(
            starting_point=self.rng.randint(0, self._width),
            current_y=self.rng.randint(0, 20),
        )

        return pipe_in_background(
            self._peripheral_manager.game_tick,
            ops.scan(lambda state, _: self._next_state(state), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _next_state(self, state: SlinkyState) -> SlinkyState:
        new_y = state.current_y + 1
        if new_y > self._height:
            return replace(
                state,
                starting_point=self.rng.randint(0, self._width),
                current_y=0,
            )
        return replace(state, current_y=new_y)

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)
from heart.utilities.reactivex_threads import pipe_in_background


class SlidingImageStateProvider(ObservableProvider[SlidingImageState]):
    def __init__(
        self,
        initial_state: SlidingImageState | None = None,
    ) -> None:
        self._initial_state = initial_state or SlidingImageState()

    def _initial_state_snapshot(self) -> SlidingImageState:
        return self._initial_state

    def reset_state(self, state: SlidingImageState) -> SlidingImageState:
        return replace(state, offset=0)

    def advance_state(self, state: SlidingImageState, width: int) -> SlidingImageState:
        if width <= 0:
            return replace(state, width=width)

        offset = (state.offset + state.speed) % width
        return replace(state, offset=offset, width=width)

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[SlidingImageState]:
        if peripheral_manager is None:
            raise ValueError("SlidingImageStateProvider requires a PeripheralManager")

        window_stream = pipe_in_background(
            peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_size()[0]),
            ops.distinct_until_changed(),
        )
        initial_state = self._initial_state_snapshot()

        return (
            pipe_in_background(
                peripheral_manager.game_tick,
                ops.with_latest_from(window_stream),
                ops.map(lambda pair: pair[1]),
                ops.scan(
                    lambda state, width: self.advance_state(state, width),
                    seed=initial_state,
                ),
                ops.start_with(initial_state),
                ops.share(),
            )
        )


class SlidingRendererStateProvider(ObservableProvider[SlidingRendererState]):
    def __init__(
        self,
        initial_state: SlidingRendererState | None = None,
    ) -> None:
        self._initial_state = initial_state or SlidingRendererState()

    def _initial_state_snapshot(self) -> SlidingRendererState:
        return self._initial_state

    def reset_state(self, state: SlidingRendererState) -> SlidingRendererState:
        return replace(state, offset=0)

    def advance_state(
        self, state: SlidingRendererState, width: int
    ) -> SlidingRendererState:
        if width <= 0:
            return replace(state, width=width)

        offset = (state.offset + state.speed) % width
        return replace(state, offset=offset, width=width)

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[SlidingRendererState]:
        if peripheral_manager is None:
            raise ValueError("SlidingRendererStateProvider requires a PeripheralManager")

        window_stream = pipe_in_background(
            peripheral_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_size()[0]),
            ops.distinct_until_changed(),
        )
        initial_state = self._initial_state_snapshot()

        return (
            pipe_in_background(
                peripheral_manager.game_tick,

                ops.with_latest_from(window_stream),
                ops.map(lambda pair: pair[1]),
                ops.scan(
                    lambda state, width: self.advance_state(state, width),
                    seed=initial_state,
                ),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

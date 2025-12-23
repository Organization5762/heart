from __future__ import annotations

from dataclasses import replace

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.sliding_image.state import (SlidingImageState,
                                                 SlidingRendererState)


class SlidingImageStateProvider(ObservableProvider[SlidingImageState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        *,
        speed: int = 1,
        width: int = 0,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._speed = max(1, speed)
        self._width = width
        self._image: pygame.Surface | None = None

    def set_width(self, width: int) -> None:
        self._width = max(0, width)

    def set_image(self, image: pygame.Surface) -> None:
        self._image = image

    def _initial_state(self) -> SlidingImageState:
        return SlidingImageState(
            speed=self._speed, width=self._width, image=self._image
        )

    def reset_state(self, state: SlidingImageState) -> SlidingImageState:
        return replace(state, offset=0)

    def advance_state(self, state: SlidingImageState) -> SlidingImageState:
        width = state.width or self._width
        if width <= 0:
            return replace(state, width=width)

        offset = (state.offset + state.speed) % width
        return replace(state, offset=offset, width=width)

    def observable(self) -> reactivex.Observable[SlidingImageState]:
        initial_state = self._initial_state()

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.scan(lambda state, _: self.advance_state(state), seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )


class SlidingRendererStateProvider(ObservableProvider[SlidingRendererState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        *,
        speed: int = 1,
        width: int = 0,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._speed = max(1, speed)
        self._width = width

    def set_width(self, width: int) -> None:
        self._width = max(0, width)

    def _initial_state(self) -> SlidingRendererState:
        return SlidingRendererState(speed=self._speed, width=self._width)

    def reset_state(self, state: SlidingRendererState) -> SlidingRendererState:
        return replace(state, offset=0)

    def advance_state(self, state: SlidingRendererState) -> SlidingRendererState:
        width = state.width or self._width
        if width <= 0:
            return replace(state, width=width)

        offset = (state.offset + state.speed) % width
        return replace(state, offset=offset, width=width)

    def observable(self) -> reactivex.Observable[SlidingRendererState]:
        initial_state = self._initial_state()

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.scan(lambda state, _: self.advance_state(state), seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

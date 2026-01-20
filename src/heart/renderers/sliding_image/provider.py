from __future__ import annotations

from dataclasses import dataclass, replace
from typing import cast

import reactivex
from reactivex import operators as ops

import pygame
from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.sliding_image.state import SlidingImageState, SlidingRendererState
from heart.utilities.reactivex_threads import pipe_in_background

SLIDING_IMAGE_DEVICE_NAME = "sliding-image"
SLIDING_RENDERER_DEVICE_NAME = "sliding-renderer"


@dataclass(frozen=True)
class SlidingStateSnapshot:
    renderer: SlidingRendererState
    image: SlidingImageState


class SlidingImageStateProvider(ObservableProvider[SlidingImageState]):
    def __init__(
        self,
        initial_state: SlidingImageState | None = None,
        peripheral_manager: PeripheralManager | None = None,
    ) -> None:
        self._initial_state = initial_state or SlidingImageState()
        self._peripheral_manager = peripheral_manager

    def _initial_state_snapshot(self) -> SlidingImageState:
        return self._initial_state

    def reset_state(self, state: SlidingImageState) -> SlidingImageState:
        return replace(state, offset=0)

    def advance_state(
        self, state: SlidingImageState, width: int
    ) -> SlidingImageState:
        return _advance_state(state, width)

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[SlidingImageState]:
        resolved_manager = peripheral_manager or self._peripheral_manager
        if resolved_manager is None:
            raise ValueError("SlidingImageStateProvider requires a PeripheralManager")

        def is_matching_peripheral(peripheral: Peripheral[object]) -> bool:
            return peripheral.device_name == SLIDING_IMAGE_DEVICE_NAME

        window_stream = pipe_in_background(
            resolved_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_width()),
            ops.distinct_until_changed(),
        )
        initial_state = self._initial_state_snapshot()
        window_stream = reactivex.merge(
            reactivex.just(initial_state.width),
            window_stream,
        )

        peripherals = [
            peripheral.observe
            for peripheral in getattr(resolved_manager, "peripherals", [])
            if is_matching_peripheral(peripheral)
        ]
        peripheral_stream = pipe_in_background(
            reactivex.merge(*peripherals) if peripherals else reactivex.empty(),
            ops.map(PeripheralMessageEnvelope[SlidingImageState].unwrap_peripheral),
        )
        return pipe_in_background(
            reactivex.merge(
                peripheral_stream,
                pipe_in_background(
                    resolved_manager.game_tick,
                    ops.with_latest_from(window_stream),
                    ops.map(lambda pair: pair[1]),
                    ops.scan(
                        lambda state, width: self.advance_state(state, width),
                        seed=initial_state,
                    ),
                    ops.start_with(initial_state),
                ),
            ),
            ops.distinct_until_changed(),
            ops.share(),
        )


class SlidingRendererStateProvider(ObservableProvider[SlidingRendererState]):
    def __init__(
        self,
        initial_state: SlidingRendererState | None = None,
        peripheral_manager: PeripheralManager | None = None,
    ) -> None:
        self._initial_state = initial_state or SlidingRendererState()
        self._peripheral_manager = peripheral_manager

    def _initial_state_snapshot(self) -> SlidingRendererState:
        return self._initial_state

    def reset_state(self, state: SlidingRendererState) -> SlidingRendererState:
        return replace(state, offset=0)

    def advance_state(
        self, state: SlidingRendererState, width: int
    ) -> SlidingRendererState:
        return _advance_state(state, width)

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[SlidingRendererState]:
        resolved_manager = peripheral_manager or self._peripheral_manager
        if resolved_manager is None:
            raise ValueError(
                "SlidingRendererStateProvider requires a PeripheralManager"
            )

        def is_matching_peripheral(peripheral: Peripheral[object]) -> bool:
            return peripheral.device_name == SLIDING_RENDERER_DEVICE_NAME

        window_stream = pipe_in_background(
            resolved_manager.window,
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: cast(pygame.Surface, window)),
            ops.map(lambda window: window.get_width()),
            ops.distinct_until_changed(),
        )
        initial_state = self._initial_state_snapshot()
        window_stream = reactivex.merge(
            reactivex.just(initial_state.width),
            window_stream,
        )

        peripherals = [
            peripheral.observe
            for peripheral in getattr(resolved_manager, "peripherals", [])
            if is_matching_peripheral(peripheral)
        ]
        peripheral_stream = pipe_in_background(
            reactivex.merge(*peripherals) if peripherals else reactivex.empty(),
            ops.map(PeripheralMessageEnvelope[SlidingRendererState].unwrap_peripheral),
        )
        return pipe_in_background(
            reactivex.merge(
                peripheral_stream,
                pipe_in_background(
                    resolved_manager.game_tick,
                    ops.with_latest_from(window_stream),
                    ops.map(lambda pair: pair[1]),
                    ops.scan(
                        lambda state, width: self.advance_state(state, width),
                        seed=initial_state,
                    ),
                    ops.start_with(initial_state),
                ),
            ),
            ops.distinct_until_changed(),
            ops.share(),
        )


def _advance_state(
    state: SlidingImageState | SlidingRendererState,
    width: int,
) -> SlidingImageState | SlidingRendererState:
    if width <= 0:
        return replace(state, width=width)

    offset = (state.offset + state.speed) % width
    return replace(state, offset=offset, width=width)

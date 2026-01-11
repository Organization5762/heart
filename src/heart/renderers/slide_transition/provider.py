from __future__ import annotations

from dataclasses import replace

import pygame
import reactivex
from reactivex import operators as ops

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.state import SlideTransitionState
from heart.runtime.display_context import DisplayContext
from heart.utilities.reactivex_threads import pipe_in_background


class SlideTransitionProvider(ObservableProvider[SlideTransitionState]):
    def __init__(
        self,
        renderer_a: StatefulBaseRenderer,
        renderer_b: StatefulBaseRenderer,
        *,
        direction: int = 1,
        slide_speed: int = 0.05,
    ) -> None:
        self.renderer_a = renderer_a
        self.renderer_b = renderer_b
        self.direction = direction
        self.slide_speed = slide_speed

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: SlideTransitionState,
    ) -> reactivex.Observable[SlideTransitionState]:

        # TODO: Switch this from game tick to clock
        tick_updates = pipe_in_background(
            peripheral_manager.game_tick,
            ops.filter(lambda tick: tick is not None),
        )

        return pipe_in_background(
            tick_updates,
            ops.scan(lambda state, update: self._advance(state=state, slide_speed=self.slide_speed), seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    @staticmethod
    def _advance(
        *,
        state: SlideTransitionState,
        slide_speed: float,
    ) -> SlideTransitionState:
        if not state.sliding:
            return state

        current_location = state.fraction_offset + slide_speed
        if current_location > 1:
            return replace(state, fraction_offset=1.0, sliding=False)

        return replace(state, fraction_offset=current_location, sliding=True)

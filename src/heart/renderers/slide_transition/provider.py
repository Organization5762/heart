from __future__ import annotations

from dataclasses import replace

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.state import SlideTransitionState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_SLIDE_DURATION_MS = 333
MIN_SLIDE_DURATION_MS = 1


class SlideTransitionProvider(ObservableProvider[SlideTransitionState]):
    def __init__(
        self,
        renderer_a: StatefulBaseRenderer,
        renderer_b: StatefulBaseRenderer,
        *,
        direction: int = 1,
        slide_duration_ms: int = DEFAULT_SLIDE_DURATION_MS,
    ) -> None:
        self.renderer_a = renderer_a
        self.renderer_b = renderer_b
        self.direction = direction
        self.slide_duration_ms = max(slide_duration_ms, MIN_SLIDE_DURATION_MS)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
        *,
        initial_state: SlideTransitionState,
    ) -> reactivex.Observable[SlideTransitionState]:

        return pipe_in_background(
            peripheral_manager.clock,
            ops.filter(lambda clock: clock is not None),
            ops.scan(
                lambda state, clock: self._advance(
                    state=state,
                    clock=clock,
                    slide_duration_ms=self.slide_duration_ms,
                ),
                seed=initial_state,
            ),
            ops.start_with(initial_state),
            ops.share(),
        )

    @staticmethod
    def _advance(
        *,
        state: SlideTransitionState,
        clock: pygame.time.Clock,
        slide_duration_ms: int,
    ) -> SlideTransitionState:
        if not state.sliding:
            return state

        delta_ms = max(float(clock.get_time()), 0.0)
        current_location = state.fraction_offset + (delta_ms / slide_duration_ms)
        if current_location >= 1:
            return replace(state, fraction_offset=1.0, sliding=False)

        return replace(state, fraction_offset=current_location, sliding=True)

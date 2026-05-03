from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.heart_title_screen.state import HeartTitleScreenState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400


class HeartTitleScreenStateProvider(ObservableProvider[HeartTitleScreenState]):
    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[HeartTitleScreenState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = HeartTitleScreenState()

        def advance_state(
            state: HeartTitleScreenState,
            frame_tick: object,
        ) -> HeartTitleScreenState:
            return self._advance_state(state=state, frame_ms=frame_tick.delta_ms)

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

    def _advance_state(
        self, *, state: HeartTitleScreenState, frame_ms: float
    ) -> HeartTitleScreenState:
        safe_frame_ms = max(frame_ms, 0.0)
        elapsed_ms = state.elapsed_ms + safe_frame_ms
        heart_up = state.heart_up

        if elapsed_ms > DEFAULT_TIME_BETWEEN_FRAMES_MS:
            elapsed_ms = 0.0
            heart_up = not heart_up

        return HeartTitleScreenState(heart_up=heart_up, elapsed_ms=elapsed_ms)

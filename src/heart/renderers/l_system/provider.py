from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.l_system.state import LSystemState
from heart.utilities.reactivex_threads import pipe_in_background


def _update_grammar(grammar: str) -> str:
    expanded = ""
    for char in grammar:
        if char == "X":
            expanded += "F+[[X]-X]-F[-FX]+X"
        elif char == "F":
            expanded += "FF"
    return expanded


def _advance_state(
    state: LSystemState, *, dt_ms: float, update_interval_ms: float
) -> LSystemState:
    accumulated = state.time_since_last_update_ms + dt_ms
    grammar = state.grammar

    while accumulated >= update_interval_ms:
        grammar = _update_grammar(grammar)
        accumulated -= update_interval_ms

    return LSystemState(grammar=grammar, time_since_last_update_ms=accumulated)


class LSystemStateProvider(ObservableProvider[LSystemState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        update_interval_ms: float = 1000.0,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._update_interval_ms = update_interval_ms

    def observable(
        self, peripheral_manager: PeripheralManager | None = None
    ) -> reactivex.Observable[LSystemState]:
        frame_ticks = pipe_in_background(
            self._peripheral_manager.frame_tick_controller.observable(),
            ops.share(),
        )

        initial_state = LSystemState()

        def advance(state: LSystemState, frame_tick: object) -> LSystemState:
            return _advance_state(
                state,
                dt_ms=float(frame_tick.delta_ms),
                update_interval_ms=self._update_interval_ms,
            )

        return (
            pipe_in_background(
                frame_ticks,
                ops.scan(advance, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

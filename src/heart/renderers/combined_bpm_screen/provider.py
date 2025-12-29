from __future__ import annotations

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.combined_bpm_screen.state import CombinedBpmScreenState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_METADATA_DURATION_MS = 12000
DEFAULT_MAX_BPM_DURATION_MS = 5000


class CombinedBpmScreenStateProvider(ObservableProvider[CombinedBpmScreenState]):
    def __init__(
        self,
        metadata_duration_ms: int = DEFAULT_METADATA_DURATION_MS,
        max_bpm_duration_ms: int = DEFAULT_MAX_BPM_DURATION_MS,
    ) -> None:
        self._metadata_duration_ms = metadata_duration_ms
        self._max_bpm_duration_ms = max_bpm_duration_ms

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[CombinedBpmScreenState]:
        clocks = pipe_in_background(
            peripheral_manager.clock,

            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = CombinedBpmScreenState()

        def advance_state(
            state: CombinedBpmScreenState, clock: Clock
        ) -> CombinedBpmScreenState:
            return self._advance_state(state=state, elapsed_ms=clock.get_time())

        return (
            pipe_in_background(
                peripheral_manager.game_tick,
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

    def _advance_state(
        self, *, state: CombinedBpmScreenState, elapsed_ms: int
    ) -> CombinedBpmScreenState:
        elapsed_time = state.elapsed_time_ms + elapsed_ms
        showing_metadata = state.showing_metadata

        if showing_metadata and elapsed_time >= self._metadata_duration_ms:
            showing_metadata = False
            elapsed_time = 0
        elif (not showing_metadata) and elapsed_time >= self._max_bpm_duration_ms:
            showing_metadata = True
            elapsed_time = 0

        return CombinedBpmScreenState(
            elapsed_time_ms=elapsed_time, showing_metadata=showing_metadata
        )

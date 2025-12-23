from __future__ import annotations

from typing import Iterable

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.heart_rates import current_bpms
from heart.renderers.metadata_screen.state import (DEFAULT_HEART_COLORS,
                                                   HeartAnimationState,
                                                   MetadataScreenState)

DEFAULT_TIME_BETWEEN_FRAMES_MS = 400


class MetadataScreenStateProvider(ObservableProvider[MetadataScreenState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        colors: Iterable[str] | None = None,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._colors = list(colors) if colors is not None else list(DEFAULT_HEART_COLORS)

    def observable(self) -> reactivex.Observable[MetadataScreenState]:
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        initial_state = MetadataScreenState()

        def advance_state(
            state: MetadataScreenState, clock: Clock
        ) -> MetadataScreenState:
            elapsed_ms = float(clock.get_time())
            active_monitors = list(current_bpms.keys())
            return self._update_state(state, active_monitors, elapsed_ms)

        return (
            self._peripheral_manager.game_tick.pipe(
                ops.with_latest_from(clocks),
                ops.map(lambda latest: latest[1]),
                ops.scan(advance_state, seed=initial_state),
                ops.start_with(initial_state),
                ops.share(),
            )
        )

    def _update_state(
        self,
        state: MetadataScreenState,
        active_monitors: list[str],
        elapsed_ms: float,
    ) -> MetadataScreenState:
        max_visible = 16
        heart_states = dict(state.heart_states)

        for i, monitor_id in enumerate(active_monitors):
            if monitor_id not in heart_states:
                heart_states[monitor_id] = HeartAnimationState(
                    up=True,
                    color_index=i % len(self._colors),
                    last_update_ms=0.0,
                )

        for monitor_id in list(heart_states.keys()):
            if monitor_id not in active_monitors:
                del heart_states[monitor_id]

        for monitor_id in active_monitors[:max_visible]:
            animation = heart_states.get(monitor_id)
            if animation is None:
                continue

            current_bpm = current_bpms.get(monitor_id, 60)
            if current_bpm > 0:
                time_between_beats = 60000 / current_bpm / 2
            else:
                time_between_beats = DEFAULT_TIME_BETWEEN_FRAMES_MS

            accumulated = animation.last_update_ms + elapsed_ms
            up = animation.up
            if accumulated > time_between_beats:
                accumulated = 0.0
                up = not animation.up

            heart_states[monitor_id] = HeartAnimationState(
                up=up,
                color_index=animation.color_index,
                last_update_ms=accumulated,
            )

        return MetadataScreenState(
            heart_states=heart_states,
            time_since_last_update_ms=state.time_since_last_update_ms + elapsed_ms,
        )

from __future__ import annotations

import random

import reactivex
from pygame.time import Clock
from reactivex import operators as ops

from heart.display.renderers.led_wave_boat.state import (LedWaveBoatFrameInput,
                                                         LedWaveBoatState)
from heart.modules.devices.acceleration.provider import \
    AllAccelerometersProvider
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.sensor import Acceleration


class LedWaveBoatStateProvider(ObservableProvider[LedWaveBoatState]):
    def __init__(
        self,
        peripheral_manager: PeripheralManager,
        accelerometers: AllAccelerometersProvider,
    ) -> None:
        self._peripheral_manager = peripheral_manager
        self._accelerometers = accelerometers
        self._rng = random.Random()

    def observable(self) -> reactivex.Observable[LedWaveBoatState]:
        window_sizes = self._peripheral_manager.window.pipe(
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
            ops.share(),
        )
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )
        accelerations = self._accelerometers.observable().pipe(
            ops.start_with(None),
            ops.share(),
        )

        frame_inputs = self._peripheral_manager.game_tick.pipe(
            ops.with_latest_from(window_sizes, clocks, accelerations),
            ops.map(self._to_frame_input),
        )

        initial_state = LedWaveBoatState.initial()

        return frame_inputs.pipe(
            ops.scan(
                lambda state, frame: state.step(frame=frame, rng=self._rng),
                seed=initial_state,
            ),
            ops.start_with(initial_state),
            ops.share(),
        )

    @staticmethod
    def _to_frame_input(
        latest: tuple[
            object | None,
            tuple[int, int],
            Clock,
            Acceleration | None,
        ]
    ) -> LedWaveBoatFrameInput:
        _, window_size, clock, acceleration = latest
        width, height = window_size
        dt = max(clock.get_time() / 1000.0, 1.0 / 120.0)

        return LedWaveBoatFrameInput(
            width=width,
            height=height,
            dt=dt,
            acceleration=acceleration,
        )

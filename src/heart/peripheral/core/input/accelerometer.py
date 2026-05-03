from __future__ import annotations

import time
from functools import cached_property
from typing import TYPE_CHECKING, cast

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.input.debug import (InputDebugStage, InputDebugTap,
                                               instrument_input_stream)
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.sensor import (Acceleration, Accelerometer,
                                     FakeAccelerometer)
from heart.utilities.env import Configuration
from heart.utilities.reactivex_threads import pipe_in_background

if TYPE_CHECKING:
    from heart.peripheral.core.input.frame import FrameTickController
    from heart.peripheral.core.input.keyboard import KeyboardController
    from heart.peripheral.core.manager import PeripheralManager

ACCELEROMETER_POLL_INTERVAL_MS = 10
DEBUG_ACCEL_SCALE = 1.5
DEBUG_ACCEL_Z_BIAS = 0.7
DEBUG_ACCEL_IMPULSE = 3.0
DEBUG_ACCEL_IMPULSE_SECONDS = 0.12


class AccelerometerController:
    def __init__(
        self,
        manager: "PeripheralManager",
        debug_tap: InputDebugTap,
    ) -> None:
        self._manager = manager
        self._debug_tap = debug_tap

    @cached_property
    def _observable(self) -> reactivex.Observable[Acceleration]:
        streams = [
            peripheral.observe
            for peripheral in self._manager.peripherals
            if isinstance(peripheral, (Accelerometer, FakeAccelerometer))
        ]
        if not streams:
            return cast(reactivex.Observable[Acceleration], reactivex.empty())

        merged = pipe_in_background(
            reactivex.merge(*streams),
            ops.map(PeripheralMessageEnvelope[Acceleration | None].unwrap_peripheral),
            ops.filter(lambda value: value is not None),
            ops.map(lambda value: cast(Acceleration, value)),
        )
        return instrument_input_stream(
            merged,
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="accelerometer.vector",
            source_id="accelerometer",
        )

    def observable(self) -> reactivex.Observable[Acceleration]:
        return self._observable


class AccelerometerDebugProfile:
    def __init__(
        self,
        keyboard_controller: "KeyboardController",
        frame_tick_controller: "FrameTickController",
        debug_tap: InputDebugTap,
        external_sensor_hub: ExternalSensorHub,
    ) -> None:
        self._keyboard_controller = keyboard_controller
        self._frame_tick_controller = frame_tick_controller
        self._debug_tap = debug_tap
        self._external_sensor_hub = external_sensor_hub
        self._space_impulse_until = 0.0

    @cached_property
    def _observable(self) -> reactivex.Observable[Acceleration | None]:
        self._keyboard_controller.key_pressed(pygame.K_SPACE).subscribe(
            on_next=lambda _event: self._arm_space_impulse()
        )

        key_states = reactivex.combine_latest(
            self._keyboard_controller.key_state(pygame.K_a),
            self._keyboard_controller.key_state(pygame.K_d),
            self._keyboard_controller.key_state(pygame.K_w),
            self._keyboard_controller.key_state(pygame.K_s),
            self._keyboard_controller.key_state(pygame.K_q),
            self._keyboard_controller.key_state(pygame.K_e),
        )

        keyboard_stream = pipe_in_background(
            self._frame_tick_controller.observable(),
            ops.with_latest_from(key_states),
            ops.map(lambda latest: self._to_acceleration(latest[0].monotonic_s, latest[1])),
            ops.distinct_until_changed(),
        )
        instrumented_keyboard_stream = instrument_input_stream(
            keyboard_stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="accelerometer.debug",
            source_id="accelerometer:debug",
            upstream_ids=(
                "frame.tick",
                "keyboard.key_state.a",
                "keyboard.key_state.d",
                "keyboard.key_state.w",
                "keyboard.key_state.s",
                "keyboard.key_state.q",
                "keyboard.key_state.e",
            ),
        )
        return pipe_in_background(
            reactivex.merge(
                self._external_sensor_hub.observable_acceleration(),
                instrumented_keyboard_stream,
            ),
            ops.distinct_until_changed(),
        )

    def observable(self) -> reactivex.Observable[Acceleration | None]:
        return self._observable

    def should_use_debug_input(self) -> bool:
        return not (Configuration.is_pi() and not Configuration.is_x11_forward())

    def _arm_space_impulse(self) -> None:
        self._space_impulse_until = time.monotonic() + DEBUG_ACCEL_IMPULSE_SECONDS

    def _to_acceleration(
        self,
        monotonic_s: float,
        key_states: tuple[object, object, object, object, object, object],
    ) -> Acceleration | None:
        state_a, state_d, state_w, state_s, state_q, state_e = key_states
        x = (float(state_d.pressed) - float(state_a.pressed)) * DEBUG_ACCEL_SCALE
        y = (float(state_w.pressed) - float(state_s.pressed)) * DEBUG_ACCEL_SCALE
        z_bias = (float(state_e.pressed) - float(state_q.pressed)) * DEBUG_ACCEL_Z_BIAS
        impulse = DEBUG_ACCEL_IMPULSE if monotonic_s <= self._space_impulse_until else 0.0
        if x == 0.0 and y == 0.0 and z_bias == 0.0 and impulse == 0.0:
            return None
        return Acceleration(x=x, y=y, z=9.81 + z_bias + impulse)

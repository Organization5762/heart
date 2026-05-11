from __future__ import annotations

import time
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, cast

import pygame
from manyfold import EmptyNode, Graph, MergeNode, StreamNode, TypedRoute

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.core.streams import (GraphRouteStream, combine_latest,
                                           runtime_route)
from heart.peripheral.core.subscriptions import CompositeSubscription
from heart.peripheral.sensor import (Acceleration, Accelerometer,
                                     FakeAccelerometer)
from heart.utilities.env import Configuration

if TYPE_CHECKING:
    from heart.peripheral.core.input.frame import FrameTickController
    from heart.peripheral.core.input.keyboard import KeyboardController
    from heart.peripheral.core.manager import PeripheralManager
ACCELEROMETER_POLL_INTERVAL_MS = 10
DEBUG_ACCEL_SCALE = 1.5
DEBUG_ACCEL_Z_BIAS = 0.7
DEBUG_ACCEL_IMPULSE = 3.0
DEBUG_ACCEL_IMPULSE_SECONDS = 0.12
ACCELERATION_ROUTE = runtime_route("accelerometer.merged", "HeartAcceleration")
DEBUG_ACCELERATION_ROUTE = runtime_route(
    "accelerometer.debug.merged", "HeartDebugAcceleration"
)


@dataclass
class AccelerometerMergeNode:
    source_streams: tuple[StreamNode[Acceleration | None], ...]
    output_route: TypedRoute[Acceleration | None]
    _subscription: CompositeSubscription | None = field(default=None, init=False)
    _latest: Acceleration | None | object = field(default=object(), init=False)

    def install(self, graph: Graph) -> CompositeSubscription:
        if self._subscription is not None:
            return self._subscription

        def publish_if_changed(value: Acceleration | None) -> None:
            if value == self._latest:
                return
            self._latest = value
            graph.publish(self.output_route, value)

        self._subscription = CompositeSubscription(
            stream.subscribe(publish_if_changed) for stream in self.source_streams
        )
        return self._subscription


class AccelerometerController:
    def __init__(self, manager: "PeripheralManager", debug_tap: InputDebugTap) -> None:
        self._manager = manager
        self._debug_tap = debug_tap
        self._graph = manager.graph
        self._stream = GraphRouteStream[Acceleration](self._graph, ACCELERATION_ROUTE)
        self._merge_subscription: CompositeSubscription | None = None

    @cached_property
    def _source_observable(self) -> StreamNode[Acceleration]:
        streams = [
            peripheral.observe
            for peripheral in self._manager.peripherals
            if isinstance(peripheral, (Accelerometer, FakeAccelerometer))
        ]
        if not streams:
            return EmptyNode().observable()
        merged = (
            MergeNode.merge(*streams)
            .map(PeripheralMessageEnvelope[Acceleration | None].unwrap_peripheral)
            .filter(lambda value: value is not None)
            .map(lambda value: cast(Acceleration, value))

        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="accelerometer.vector",
            source_id="accelerometer",
        ).connect(merged)

    def node(self) -> GraphRouteStream[Acceleration]:
        if self._merge_subscription is None:
            self._merge_subscription = AccelerometerMergeNode(
                source_streams=(self._source_observable,),
                output_route=ACCELERATION_ROUTE,
            ).install(self._graph)
        return self._stream

    def observable(self) -> StreamNode[Acceleration]:
        return self.node()


class AccelerometerDebugProfile:
    def __init__(
        self,
        keyboard_controller: "KeyboardController",
        frame_tick_controller: "FrameTickController",
        debug_tap: InputDebugTap,
        external_sensor_hub: ExternalSensorHub,
        graph: Graph | None = None,
    ) -> None:
        self._keyboard_controller = keyboard_controller
        self._frame_tick_controller = frame_tick_controller
        self._debug_tap = debug_tap
        self._external_sensor_hub = external_sensor_hub
        self._graph = graph or Graph()
        self._debug_stream = GraphRouteStream[Acceleration | None](
            self._graph, DEBUG_ACCELERATION_ROUTE
        )
        self._merge_subscription: CompositeSubscription | None = None
        self._space_impulse_until = 0.0

    @cached_property
    def _keyboard_observable(self) -> StreamNode[Acceleration | None]:
        self._keyboard_controller.key_pressed(pygame.K_SPACE).subscribe(
            on_next=lambda _event: self._arm_space_impulse()
        )
        key_states = combine_latest(
            self._keyboard_controller.key_state(pygame.K_a),
            self._keyboard_controller.key_state(pygame.K_d),
            self._keyboard_controller.key_state(pygame.K_w),
            self._keyboard_controller.key_state(pygame.K_s),
            self._keyboard_controller.key_state(pygame.K_q),
            self._keyboard_controller.key_state(pygame.K_e),
        )
        keyboard_stream = (
            self._frame_tick_controller.observable()
            .with_latest_from(key_states)
            .map(lambda latest: self._to_acceleration(latest[0].monotonic_s, latest[1]))
            .distinct_until_changed()

        )
        instrumented_keyboard_stream = InputDebugNode(
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
        ).connect(keyboard_stream)
        return instrumented_keyboard_stream

    def node(self) -> GraphRouteStream[Acceleration | None]:
        if self._merge_subscription is None:
            self._merge_subscription = AccelerometerMergeNode(
                source_streams=(
                    self._external_sensor_hub.observable_acceleration(),
                    self._keyboard_observable,
                ),
                output_route=DEBUG_ACCELERATION_ROUTE,
            ).install(self._graph)
        return self._debug_stream

    def observable(self) -> StreamNode[Acceleration | None]:
        return self.node()

    def should_use_debug_input(self) -> bool:
        return not (Configuration.is_pi() and (not Configuration.is_x11_forward()))

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
        impulse = (
            DEBUG_ACCEL_IMPULSE if monotonic_s <= self._space_impulse_until else 0.0
        )
        if x == 0.0 and y == 0.0 and (z_bias == 0.0) and (impulse == 0.0):
            return None
        return Acceleration(x=x, y=y, z=9.81 + z_bias + impulse)

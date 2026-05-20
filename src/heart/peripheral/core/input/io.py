from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import cached_property
from typing import Any, TypeVar, cast

import pygame
from manyfold import EmptyNode, Graph, MergeNode, StreamNode

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.core.input.accelerometer import (
    AccelerometerController, AccelerometerDebugProfile)
from heart.peripheral.core.input.color import ColorInputProfile
from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.core.input.frame import FrameTick, FrameTickController
from heart.peripheral.core.input.gamepad import (GamepadController,
                                                 GamepadSnapshot)
from heart.peripheral.core.input.keyboard import (KeyboardController,
                                                  KeyboardSnapshot)
from heart.peripheral.core.input.peripheral_inputs import PeripheralInputBus
from heart.peripheral.core.input.profiles.mandelbrot import (
    MandelbrotControlProfile, MandelbrotControlState)
from heart.peripheral.core.input.profiles.navigation import (
    ActivateIntent, AlternateActivateIntent, BrowseIntent, NavigationIntent,
    NavigationProfile)
from heart.peripheral.core.input.streams import map_stream, merge_streams
from heart.peripheral.core.streams import (EventStream, GraphRouteStream,
                                           runtime_route)
from heart.peripheral.sensor import (Acceleration, Accelerometer,
                                     FakeAccelerometer)
from heart.peripheral.switch import BaseSwitch, FakeSwitch, SwitchState

FINAL_FRAME_ROUTE = runtime_route("window", "HeartRuntimeWindow")
PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]
TNavigationIntent = TypeVar("TNavigationIntent", bound=NavigationIntent)


@dataclass
class InputIO:
    """Explicit wiring for Heart's input stream graph.

    Raw sources stay visible here: hardware peripherals become manyfold streams,
    logical controllers read those streams, and profile-level streams merge
    keyboard/gamepad/switch/debug input into the contracts renderers consume.
    """

    graph: Graph
    peripheral_source: PeripheralSource

    @cached_property
    def debug_tap(self) -> InputDebugTap:
        return InputDebugTap()

    @cached_property
    def frame_ticks(self) -> FrameTickController:
        return FrameTickController(self.debug_tap, graph=self.graph)

    @cached_property
    def keyboard(self) -> KeyboardController:
        return KeyboardController(self.debug_tap)

    @cached_property
    def gamepad(self) -> GamepadController:
        return GamepadController(self, self.debug_tap)

    @cached_property
    def external_sensors(self) -> ExternalSensorHub:
        return ExternalSensorHub(self.debug_tap, graph=self.graph)

    @cached_property
    def peripheral_inputs(self) -> PeripheralInputBus:
        return PeripheralInputBus(
            debug_tap=self.debug_tap,
            peripheral_source=self.peripheral_source,
        )

    @cached_property
    def color(self) -> ColorInputProfile:
        return ColorInputProfile(
            final_frames=self.final_frame_stream(),
            debug_tap=self.debug_tap,
        )

    @cached_property
    def injected_navigation_intents(self) -> EventStream[NavigationIntent]:
        return EventStream()

    @cached_property
    def navigation(self) -> NavigationProfile:
        return NavigationProfile(
            intents=self.navigation_intents(),
            injected_intents=self.injected_navigation_intents,
        )

    @cached_property
    def accelerometer(self) -> AccelerometerController:
        return AccelerometerController(
            graph=self.graph,
            source_stream=self.all_accelerometers,
        )

    @cached_property
    def debug_accelerometer(self) -> AccelerometerDebugProfile:
        return AccelerometerDebugProfile(
            keyboard_controller=self.keyboard,
            frame_tick_controller=self.frame_ticks,
            debug_tap=self.debug_tap,
            external_sensor_hub=self.external_sensors,
            graph=self.graph,
        )

    @cached_property
    def mandelbrot(self) -> MandelbrotControlProfile:
        return MandelbrotControlProfile(
            keyboard_controller=self.keyboard,
            gamepad_controller=self.gamepad,
            debug_tap=self.debug_tap,
        )

    @property
    def peripherals(self) -> tuple[Peripheral[Any], ...]:
        return tuple(self.peripheral_source())

    def main_switch_stream(self) -> StreamNode[SwitchState]:
        return self._switch_stream(include_fake_switches=True)

    def physical_main_switch_stream(self) -> StreamNode[SwitchState]:
        return self._switch_stream(include_fake_switches=False)

    def _switch_stream(self, *, include_fake_switches: bool) -> StreamNode[SwitchState]:
        streams = [
            peripheral.observe
            for peripheral in self.peripherals
            if isinstance(peripheral, BaseSwitch)
            and (include_fake_switches or not isinstance(peripheral, FakeSwitch))
        ]
        if not streams:
            return EmptyNode().observable()
        return MergeNode.merge(*streams).map(
            PeripheralMessageEnvelope[SwitchState].unwrap_peripheral
        )

    @cached_property
    def all_accelerometers(self) -> StreamNode[Acceleration]:
        streams = [
            peripheral.observe
            for peripheral in self.peripherals
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
            tap=self.debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="accelerometer.vector",
            source_id="accelerometer",
        ).connect(merged)

    def keyboard_snapshots(self) -> StreamNode[KeyboardSnapshot]:
        return self.keyboard.snapshot_stream()

    def gamepad_snapshots(self) -> StreamNode[GamepadSnapshot]:
        return self.gamepad.snapshot_stream()

    def frame_tick_stream(self) -> StreamNode[FrameTick]:
        return self.frame_ticks.observable()

    def final_frame_stream(self) -> GraphRouteStream[pygame.Surface]:
        return GraphRouteStream(self.graph, FINAL_FRAME_ROUTE)

    def physical_acceleration(self) -> GraphRouteStream[Acceleration]:
        return self.accelerometer.node()

    def debug_acceleration(self) -> GraphRouteStream[Acceleration | None]:
        return self.debug_accelerometer.node()

    def active_acceleration(self) -> StreamNode[Acceleration | None]:
        if self.debug_accelerometer.should_use_debug_input():
            return self.debug_acceleration()
        return self.physical_acceleration()

    @cached_property
    def navigation_intent_stream(self) -> StreamNode[NavigationIntent]:
        keyboard_left = map_stream(
            self.keyboard.key_pressed(pygame.K_LEFT),
            lambda _event: BrowseIntent(source="keyboard.left", step=-1),
        )
        keyboard_right = map_stream(
            self.keyboard.key_pressed(pygame.K_RIGHT),
            lambda _event: BrowseIntent(source="keyboard.right", step=1),
        )
        keyboard_down = map_stream(
            self.keyboard.key_pressed(pygame.K_DOWN),
            lambda _event: ActivateIntent(source="keyboard.down"),
        )
        keyboard_up = map_stream(
            self.keyboard.key_pressed(pygame.K_UP),
            lambda _event: AlternateActivateIntent(source="keyboard.up"),
        )
        stream = merge_streams(
            keyboard_left,
            keyboard_right,
            keyboard_down,
            keyboard_up,
            self.switch_navigation_intents(),
            self.injected_navigation_intents,
        )
        return InputDebugNode(
            tap=self.debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.intent",
            source_id=lambda intent: intent.source,
            upstream_ids=(
                "keyboard.pressed.left",
                "keyboard.pressed.right",
                "keyboard.pressed.down",
                "keyboard.pressed.up",
                "switch.rotational_value",
                "switch.button_value",
                "switch.long_button_value",
            ),
        ).connect(stream)

    def navigation_intents(self) -> StreamNode[NavigationIntent]:
        return self.navigation_intent_stream

    def mandelbrot_controls(self) -> StreamNode[MandelbrotControlState]:
        return self.mandelbrot.observable()

    def switch_navigation_intents(self) -> StreamNode[NavigationIntent]:
        switch_updates = self.physical_main_switch_stream()
        return MergeNode.merge(
            self.switch_browse_intents(switch_updates),
            self.switch_activate_intents(switch_updates),
            self.switch_alternate_activate_intents(switch_updates),
        )

    def switch_browse_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[BrowseIntent]:
        return (
            switch_updates.pairwise()
            .map(lambda latest: latest[1].rotational_value - latest[0].rotational_value)
            .filter(lambda delta: delta != 0)
            .map(lambda delta: BrowseIntent(source="switch.rotary", step=delta))
        )

    def switch_activate_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[ActivateIntent]:
        return _counter_increase_intents(
            switch_updates,
            lambda state: state.button_value,
            lambda: ActivateIntent(source="switch.button"),
        )

    def switch_alternate_activate_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[AlternateActivateIntent]:
        return _counter_increase_intents(
            switch_updates,
            lambda state: state.long_button_value,
            lambda: AlternateActivateIntent(source="switch.long_button"),
        )


def _counter_increase_intents(
    source: StreamNode[SwitchState],
    counter_value: Callable[[SwitchState], int],
    create_intent: Callable[[], TNavigationIntent],
) -> StreamNode[TNavigationIntent]:
    output: EventStream[TNavigationIntent] = EventStream()
    previous: int | None = None

    def emit_increases(state: SwitchState) -> None:
        nonlocal previous
        current = counter_value(state)
        if previous is not None:
            for _ in range(max(0, current - previous)):
                output.emit(create_intent())
        previous = current

    source.subscribe(emit_increases)
    return output

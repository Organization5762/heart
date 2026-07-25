from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, TypeVar, cast

import pygame
from manyfold import EmptyNode, Graph, Subscribable
from manyfold.architecture import NewValues, PubSubObservable

from heart.peripheral.core import Peripheral, PeripheralMessageEnvelope
from heart.peripheral.core.input.accelerometer import (
    AccelerometerController, AccelerometerDebugProfile)
from heart.peripheral.core.input.color import ColorInputProfile
from heart.peripheral.core.input.controls import ControlSurface
from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.core.input.frame import FrameTick, FrameTickController
from heart.peripheral.core.input.gamepad import (GamepadController,
                                                 GamepadSnapshotEvent)
from heart.peripheral.core.input.keyboard import (KeyboardController,
                                                  KeyboardSnapshot)
from heart.peripheral.core.input.peripheral_inputs import PeripheralInputBus
from heart.peripheral.core.input.profiles.mandelbrot import (
    MandelbrotControlProfile, MandelbrotControlState)
from heart.peripheral.core.input.profiles.navigation import (
    ActivateIntent, AlternateActivateIntent, BrowseIntent, NavigationIntent,
    NavigationProfile)
from heart.peripheral.core.streams import GraphRouteStream, runtime_route
from heart.peripheral.sensor import (Acceleration, Accelerometer,
                                     FakeAccelerometer)
from heart.peripheral.switch import BaseSwitch, FakeSwitch, SwitchState
from heart.utilities.env import Configuration

FINAL_FRAME_ROUTE = runtime_route("window", "HeartRuntimeWindow")
PeripheralSource = Callable[[], Iterable[Peripheral[Any]]]
TNavigationIntent = TypeVar("TNavigationIntent", bound=NavigationIntent)


@dataclass
class SwitchStateEvent:
    source_id: str
    state: SwitchState


@dataclass
class InputIO:
    """Explicit wiring for Heart's input stream graph.

    Raw sources stay visible here: hardware peripherals become manyfold streams,
    logical controllers read those streams, and profile-level streams merge
    keyboard/gamepad/switch/debug input into the contracts renderers consume.
    """

    graph: Graph
    peripheral_source: PeripheralSource
    _subscriptions: list[Any] = field(default_factory=list, init=False)

    @cached_property
    def debug_tap(self) -> InputDebugTap:
        if Configuration.is_debug_mode() or Configuration.stream_beats_input_debug():
            return InputDebugTap()
        return InputDebugTap(history_size=0, latency_history_size=0)

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
    def navigation(self) -> NavigationProfile:
        return NavigationProfile(intents=self._navigation_source_intents)

    @cached_property
    def controls(self) -> ControlSurface:
        return ControlSurface(self.keyboard, self.gamepad)

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

    def main_switch_stream(self) -> Subscribable[SwitchStateEvent]:
        return self._switch_stream(include_fake_switches=True)

    def physical_main_switch_stream(self) -> Subscribable[SwitchStateEvent]:
        return self._switch_stream(include_fake_switches=False)

    def _switch_stream(
        self, *, include_fake_switches: bool
    ) -> Subscribable[SwitchStateEvent]:
        streams = [
            peripheral.observe
            for peripheral in self.peripherals
            if isinstance(peripheral, BaseSwitch)
            and (include_fake_switches or not isinstance(peripheral, FakeSwitch))
        ]
        if not streams:
            return EmptyNode().observable()
        return PubSubObservable.merge(*streams).map(_switch_state_event)

    @cached_property
    def all_accelerometers(self) -> Subscribable[Acceleration]:
        streams = [
            peripheral.observe
            for peripheral in self.peripherals
            if isinstance(peripheral, (Accelerometer, FakeAccelerometer))
        ]
        if not streams:
            return EmptyNode().observable()
        merged = (
            PubSubObservable.merge(*streams)
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

    def keyboard_snapshots(self) -> Subscribable[KeyboardSnapshot]:
        return self.keyboard.snapshot_stream()

    def frame_tick_stream(self) -> Subscribable[FrameTick]:
        return self.frame_ticks.observable()

    def final_frame_stream(self) -> GraphRouteStream[pygame.Surface]:
        return GraphRouteStream(self.graph, FINAL_FRAME_ROUTE)

    def physical_acceleration(self) -> GraphRouteStream[Acceleration]:
        return self.accelerometer.node()

    def debug_acceleration(self) -> GraphRouteStream[Acceleration | None]:
        return self.debug_accelerometer.node()

    def active_acceleration(self) -> Subscribable[Acceleration | None]:
        if self.debug_accelerometer.should_use_debug_input():
            return self.debug_acceleration()
        return self.physical_acceleration()

    def poll(
        self,
    ) -> tuple[KeyboardSnapshot, tuple[GamepadSnapshotEvent, ...]]:
        gamepads = self.gamepad.poll()
        keyboard = self.keyboard.poll()
        return keyboard, gamepads

    def close(self) -> None:
        if "navigation" in self.__dict__:
            self.navigation.close()
        if "keyboard" in self.__dict__:
            self.keyboard.close()
        for subscription in reversed(self._subscriptions):
            subscription.dispose()
        self._subscriptions.clear()

    @cached_property
    def navigation_intent_stream(self) -> Subscribable[NavigationIntent]:
        return self.navigation.intents

    @cached_property
    def _navigation_source_intents(self) -> Subscribable[NavigationIntent]:
        stream = self.switch_navigation_intents()
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

    def navigation_intents(self) -> Subscribable[NavigationIntent]:
        return self.navigation_intent_stream

    def mandelbrot_controls(self) -> Subscribable[MandelbrotControlState]:
        return self.mandelbrot.observable()

    def switch_navigation_intents(self) -> Subscribable[NavigationIntent]:
        switch_updates = self.physical_main_switch_stream()
        return PubSubObservable.merge(
            self.switch_browse_intents(switch_updates),
            self.switch_activate_intents(switch_updates),
            self.switch_alternate_activate_intents(switch_updates),
        )

    def switch_browse_intents(
        self, switch_updates: Subscribable[SwitchStateEvent]
    ) -> Subscribable[BrowseIntent]:
        output = NewValues[BrowseIntent](name="heart.input.switch.browse_intents")
        previous_by_source: dict[str, int] = {}

        def emit_delta(event: SwitchStateEvent) -> None:
            previous = previous_by_source.get(event.source_id)
            current = event.state.rotational_value
            if previous is not None:
                delta = current - previous
                if delta != 0:
                    output.emit(BrowseIntent(source="switch.rotary", step=delta))
            previous_by_source[event.source_id] = current

        self._subscriptions.append(switch_updates.subscribe(emit_delta))
        return output

    def switch_activate_intents(
        self, switch_updates: Subscribable[SwitchStateEvent]
    ) -> Subscribable[ActivateIntent]:
        return self._counter_increase_intents(
            switch_updates,
            lambda event: event.state.button_value,
            lambda: ActivateIntent(source="switch.button"),
        )

    def switch_alternate_activate_intents(
        self, switch_updates: Subscribable[SwitchStateEvent]
    ) -> Subscribable[AlternateActivateIntent]:
        return self._counter_increase_intents(
            switch_updates,
            lambda event: event.state.long_button_value,
            lambda: AlternateActivateIntent(source="switch.long_button"),
        )

    def _counter_increase_intents(
        self,
        source: Subscribable[SwitchStateEvent],
        counter_value: Callable[[SwitchStateEvent], int],
        create_intent: Callable[[], TNavigationIntent],
    ) -> Subscribable[TNavigationIntent]:
        output = NewValues[TNavigationIntent](name="heart.input.switch.counter_intents")
        previous_by_source: dict[str, int] = {}

        def emit_increases(event: SwitchStateEvent) -> None:
            previous = previous_by_source.get(event.source_id)
            current = counter_value(event)
            if previous is not None:
                for _ in range(max(0, current - previous)):
                    output.emit(create_intent())
            previous_by_source[event.source_id] = current

        self._subscriptions.append(source.subscribe(emit_increases))
        return output


def _switch_state_event(
    envelope: PeripheralMessageEnvelope[SwitchState],
) -> SwitchStateEvent:
    source_id = envelope.peripheral_info.id or "switch:unknown"
    return SwitchStateEvent(source_id=source_id, state=envelope.data)

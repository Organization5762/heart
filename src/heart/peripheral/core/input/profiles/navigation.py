from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from typing import TypeVar

import pygame
from manyfold import CompositeSubscription, MergeNode, StreamNode

from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.gamepad import (
    DEFAULT_GAMEPAD_AXIS_DEAD_ZONE, GamepadAxis, GamepadButton,
    GamepadController)
from heart.peripheral.core.input.keyboard import KeyboardController
from heart.peripheral.core.input.streams import (map_stream, merge_streams,
                                                 threshold_direction)
from heart.peripheral.core.nodes import empty_node
from heart.peripheral.core.streams import EventStream
from heart.peripheral.switch import SwitchState

NAVIGATION_STICK_THRESHOLD = 0.6


@dataclass(frozen=True, slots=True)
class _NavigationIntent:
    source: str


@dataclass(frozen=True, slots=True)
class BrowseIntent(_NavigationIntent):
    step: int


@dataclass(frozen=True, slots=True)
class ActivateIntent(_NavigationIntent):
    pass


@dataclass(frozen=True, slots=True)
class AlternateActivateIntent(_NavigationIntent):
    pass


NavigationIntent = BrowseIntent | ActivateIntent | AlternateActivateIntent
TNavigationIntent = TypeVar("TNavigationIntent", bound=_NavigationIntent)


def _counter_increase_intents(
    source: StreamNode[SwitchState],
    counter_value: Callable[[SwitchState], int],
    create_intent: Callable[[], TNavigationIntent],
    *,
    stream_name: str,
) -> StreamNode[TNavigationIntent]:
    del stream_name
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


class NavigationProfile:
    def __init__(
        self,
        keyboard_controller: KeyboardController,
        gamepad_controller: GamepadController,
        debug_tap: InputDebugTap,
        switch_stream_factory: Callable[[], StreamNode[SwitchState]] | None = None,
    ) -> None:
        self._keyboard = keyboard_controller
        self._gamepad = gamepad_controller
        self._debug_tap = debug_tap
        self._switch_stream_factory = switch_stream_factory
        self._injected_intents: EventStream[NavigationIntent] = EventStream()

    def subscribe_events(
        self,
        *,
        on_browse: Callable[[BrowseIntent], None] | None = None,
        on_browse_delta: Callable[[int], None] | None = None,
        on_activate: Callable[[ActivateIntent], None] | None = None,
        on_alternate_activate: Callable[[AlternateActivateIntent], None] | None = None,
    ) -> CompositeSubscription:
        subscriptions = []
        if on_browse is not None:
            subscriptions.append(self.browse.subscribe(on_next=on_browse))
        if on_browse_delta is not None:
            subscriptions.append(self.browse_delta.subscribe(on_next=on_browse_delta))
        if on_activate is not None:
            subscriptions.append(self.activate.subscribe(on_next=on_activate))
        if on_alternate_activate is not None:
            subscriptions.append(
                self.alternate_activate.subscribe(on_next=on_alternate_activate)
            )
        return CompositeSubscription(subscriptions)

    @cached_property
    def intents(self) -> StreamNode[NavigationIntent]:
        keyboard_left = map_stream(
            self._keyboard.key_pressed(pygame.K_LEFT),
            lambda _event: BrowseIntent(source="keyboard.left", step=-1),
        )
        keyboard_right = map_stream(
            self._keyboard.key_pressed(pygame.K_RIGHT),
            lambda _event: BrowseIntent(source="keyboard.right", step=1),
        )
        keyboard_down = map_stream(
            self._keyboard.key_pressed(pygame.K_DOWN),
            lambda _event: ActivateIntent(source="keyboard.down"),
        )
        keyboard_up = map_stream(
            self._keyboard.key_pressed(pygame.K_UP),
            lambda _event: AlternateActivateIntent(source="keyboard.up"),
        )
        dpad_events = (
            self._gamepad.dpad_value()
            .pairwise()
            .filter(lambda latest: latest[0].x != latest[1].x and latest[1].x != 0)
            .map(lambda latest: BrowseIntent(source="gamepad.dpad", step=latest[1].x))

        )
        stick_events = (
            self._gamepad.axis_value(GamepadAxis.LEFT_X, DEFAULT_GAMEPAD_AXIS_DEAD_ZONE)
            .map(lambda value: threshold_direction(value, NAVIGATION_STICK_THRESHOLD))
            .distinct_until_changed()
            .filter(lambda direction: direction != 0)
            .map(
                lambda direction: BrowseIntent(
                    source="gamepad.left_stick", step=direction
                )
            )

        )
        button_south = map_stream(
            self._gamepad.button_tapped(GamepadButton.SOUTH),
            lambda _button: ActivateIntent(source="gamepad.south"),
        )
        button_north = map_stream(
            self._gamepad.button_tapped(GamepadButton.NORTH),
            lambda _button: AlternateActivateIntent(source="gamepad.north"),
        )
        switch_intents = self._switch_intents()
        stream = merge_streams(
            keyboard_left,
            keyboard_right,
            keyboard_down,
            keyboard_up,
            dpad_events,
            stick_events,
            button_south,
            button_north,
            switch_intents,
            self._injected_intents,
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.intent",
            source_id=lambda intent: intent.source,
            upstream_ids=(
                "keyboard.pressed.left",
                "keyboard.pressed.right",
                "keyboard.pressed.down",
                "keyboard.pressed.up",
                "gamepad.dpad",
                "gamepad.axis.left_x",
                "gamepad.button_tapped.south",
                "gamepad.button_tapped.north",
                "switch.rotational_value",
                "switch.button_value",
                "switch.long_button_value",
            ),
        ).connect(stream)

    @cached_property
    def browse(self) -> StreamNode[BrowseIntent]:
        return (
            self.intents.filter(lambda intent: isinstance(intent, BrowseIntent))
            .map(lambda intent: intent)

        )

    @cached_property
    def activate(self) -> StreamNode[ActivateIntent]:
        return (
            self.intents.filter(lambda intent: isinstance(intent, ActivateIntent))
            .map(lambda intent: intent)

        )

    @cached_property
    def alternate_activate(self) -> StreamNode[AlternateActivateIntent]:
        return (
            self.intents.filter(
                lambda intent: isinstance(intent, AlternateActivateIntent)
            )
            .map(lambda intent: intent)

        )

    @cached_property
    def browse_delta(self) -> StreamNode[int]:
        return self.browse.map(lambda intent: intent.step)

    def inject_browse(self, step: int, source: str = "beats.control") -> None:
        if step == 0:
            return
        self._injected_intents.emit(BrowseIntent(source=source, step=step))

    def inject_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.emit(ActivateIntent(source=source))

    def inject_alternate_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.emit(AlternateActivateIntent(source=source))

    def _switch_intents(self) -> StreamNode[NavigationIntent]:
        if self._switch_stream_factory is None:
            return empty_node()
        switch_updates = self._switch_stream_factory()
        return MergeNode.merge(
            self._switch_browse_intents(switch_updates),
            self._switch_activate_intents(switch_updates),
            self._switch_alternate_activate_intents(switch_updates),
        )

    def _switch_browse_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[BrowseIntent]:
        return (
            switch_updates.pairwise()
            .map(lambda latest: latest[1].rotational_value - latest[0].rotational_value)
            .filter(lambda delta: delta != 0)
            .map(lambda delta: BrowseIntent(source="switch.rotary", step=delta))

        )

    def _switch_activate_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[ActivateIntent]:
        return _counter_increase_intents(
            switch_updates,
            lambda state: state.button_value,
            lambda: ActivateIntent(source="switch.button"),
            stream_name="navigation.switch.button",
        )

    def _switch_alternate_activate_intents(
        self, switch_updates: StreamNode[SwitchState]
    ) -> StreamNode[AlternateActivateIntent]:
        return _counter_increase_intents(
            switch_updates,
            lambda state: state.long_button_value,
            lambda: AlternateActivateIntent(source="switch.long_button"),
            stream_name="navigation.switch.long_button",
        )

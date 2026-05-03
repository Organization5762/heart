from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

import pygame

import heart.utilities.reactive as reactive
from heart.peripheral.core.input.debug import (InputDebugStage, InputDebugTap,
                                               instrument_input_stream)
from heart.peripheral.core.input.gamepad import (
    DEFAULT_GAMEPAD_AXIS_DEAD_ZONE, GamepadAxis, GamepadButton,
    GamepadController)
from heart.peripheral.core.input.keyboard import KeyboardController
from heart.peripheral.core.input.streams import (map_stream, merge_streams,
                                                 threshold_direction)
from heart.peripheral.switch import SwitchState
from heart.utilities.reactive import (CompositeDisposable, DisposableBase,
                                      Subject)
from heart.utilities.reactive import operators as ops
from heart.utilities.reactive_threads import pipe_in_background

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


class NavigationProfile:
    def __init__(
        self,
        keyboard_controller: KeyboardController,
        gamepad_controller: GamepadController,
        debug_tap: InputDebugTap,
        switch_stream_factory: Callable[[], reactive.Observable[SwitchState]]
        | None = None,
    ) -> None:
        self._keyboard = keyboard_controller
        self._gamepad = gamepad_controller
        self._debug_tap = debug_tap
        self._switch_stream_factory = switch_stream_factory
        self._injected_intents: Subject[NavigationIntent] = Subject()

    def subscribe_events(
        self,
        *,
        on_browse: Callable[[BrowseIntent], None] | None = None,
        on_browse_delta: Callable[[int], None] | None = None,
        on_activate: Callable[[ActivateIntent], None] | None = None,
        on_alternate_activate: Callable[[AlternateActivateIntent], None] | None = None,
    ) -> DisposableBase:
        subscriptions: list[DisposableBase] = []
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
        return CompositeDisposable(*subscriptions)

    @cached_property
    def intents(self) -> reactive.Observable[NavigationIntent]:
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
        dpad_events = pipe_in_background(
            self._gamepad.dpad_value(),
            ops.pairwise(),
            ops.filter(lambda latest: latest[0].x != latest[1].x and latest[1].x != 0),
            ops.map(
                lambda latest: BrowseIntent(
                    source="gamepad.dpad",
                    step=latest[1].x,
                )
            ),
        )
        stick_events = pipe_in_background(
            self._gamepad.axis_value(
                GamepadAxis.LEFT_X,
                DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
            ),
            ops.map(lambda value: threshold_direction(value, NAVIGATION_STICK_THRESHOLD)),
            ops.distinct_until_changed(),
            ops.filter(lambda direction: direction != 0),
            ops.map(
                lambda direction: BrowseIntent(
                    source="gamepad.left_stick",
                    step=direction,
                )
            ),
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
            pipe_in_background(self._injected_intents),
        )
        return instrument_input_stream(
            stream,
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
        )

    @cached_property
    def browse(self) -> reactive.Observable[BrowseIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(lambda intent: isinstance(intent, BrowseIntent)),
            ops.map(lambda intent: intent),
        )

    @cached_property
    def activate(self) -> reactive.Observable[ActivateIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(lambda intent: isinstance(intent, ActivateIntent)),
            ops.map(lambda intent: intent),
        )

    @cached_property
    def alternate_activate(self) -> reactive.Observable[AlternateActivateIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(lambda intent: isinstance(intent, AlternateActivateIntent)),
            ops.map(lambda intent: intent),
        )

    @cached_property
    def browse_delta(self) -> reactive.Observable[int]:
        return pipe_in_background(
            self.browse,
            ops.map(lambda intent: intent.step),
        )

    def inject_browse(self, step: int, source: str = "beats.control") -> None:
        if step == 0:
            return
        self._injected_intents.on_next(BrowseIntent(source=source, step=step))

    def inject_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.on_next(ActivateIntent(source=source))

    def inject_alternate_activate(self, source: str = "beats.control") -> None:
        self._injected_intents.on_next(AlternateActivateIntent(source=source))

    def _switch_intents(self) -> reactive.Observable[NavigationIntent]:
        if self._switch_stream_factory is None:
            return reactive.empty()

        switch_updates = self._switch_stream_factory()
        return reactive.merge(
            self._switch_browse_intents(switch_updates),
            self._switch_activate_intents(switch_updates),
            self._switch_alternate_activate_intents(switch_updates),
        )

    def _switch_browse_intents(
        self,
        switch_updates: reactive.Observable[SwitchState],
    ) -> reactive.Observable[BrowseIntent]:
        return pipe_in_background(
            switch_updates,
            ops.pairwise(),
            ops.map(
                lambda latest: latest[1].rotational_value - latest[0].rotational_value
            ),
            ops.filter(lambda delta: delta != 0),
            ops.map(
                lambda delta: BrowseIntent(
                    source="switch.rotary",
                    step=delta,
                )
            ),
        )

    def _switch_activate_intents(
        self,
        switch_updates: reactive.Observable[SwitchState],
    ) -> reactive.Observable[ActivateIntent]:
        return pipe_in_background(
            switch_updates,
            ops.pairwise(),
            ops.map(lambda latest: latest[1].button_value - latest[0].button_value),
            ops.filter(lambda delta: delta > 0),
            ops.flat_map(
                lambda delta: reactive.from_iterable(
                    ActivateIntent(source="switch.button")
                    for _ in range(delta)
                )
            ),
        )

    def _switch_alternate_activate_intents(
        self,
        switch_updates: reactive.Observable[SwitchState],
    ) -> reactive.Observable[AlternateActivateIntent]:
        return pipe_in_background(
            switch_updates,
            ops.pairwise(),
            ops.map(
                lambda latest: latest[1].long_button_value
                - latest[0].long_button_value
            ),
            ops.filter(lambda delta: delta > 0),
            ops.flat_map(
                lambda delta: reactive.from_iterable(
                    AlternateActivateIntent(source="switch.long_button")
                    for _ in range(delta)
                )
            ),
        )

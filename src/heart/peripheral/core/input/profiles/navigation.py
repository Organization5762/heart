from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.input.debug import (InputDebugStage, InputDebugTap,
                                               instrument_input_stream)
from heart.peripheral.core.input.gamepad import (
    DEFAULT_GAMEPAD_AXIS_DEAD_ZONE, GamepadAxis, GamepadButton,
    GamepadController)
from heart.peripheral.core.input.keyboard import KeyboardController
from heart.utilities.reactivex_threads import pipe_in_background

NAVIGATION_STICK_THRESHOLD = 0.6


class NavigationIntentKind(StrEnum):
    BROWSE = "browse"
    ACTIVATE = "activate"
    ALTERNATE_ACTIVATE = "alternate_activate"


@dataclass(frozen=True, slots=True)
class NavigationIntent:
    kind: NavigationIntentKind
    source: str
    step: int = 0


class NavigationProfile:
    def __init__(
        self,
        keyboard_controller: KeyboardController,
        gamepad_controller: GamepadController,
        debug_tap: InputDebugTap,
    ) -> None:
        self._keyboard = keyboard_controller
        self._gamepad = gamepad_controller
        self._debug_tap = debug_tap

    @cached_property
    def intents(self) -> reactivex.Observable[NavigationIntent]:
        keyboard_left = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_LEFT),
            ops.map(
                lambda _event: NavigationIntent(
                    kind=NavigationIntentKind.BROWSE,
                    source="keyboard.left",
                    step=-1,
                )
            ),
        )
        keyboard_right = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_RIGHT),
            ops.map(
                lambda _event: NavigationIntent(
                    kind=NavigationIntentKind.BROWSE,
                    source="keyboard.right",
                    step=1,
                )
            ),
        )
        keyboard_down = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_DOWN),
            ops.map(
                lambda _event: NavigationIntent(
                    kind=NavigationIntentKind.ACTIVATE,
                    source="keyboard.down",
                )
            ),
        )
        keyboard_up = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_UP),
            ops.map(
                lambda _event: NavigationIntent(
                    kind=NavigationIntentKind.ALTERNATE_ACTIVATE,
                    source="keyboard.up",
                )
            ),
        )
        dpad_events = pipe_in_background(
            self._gamepad.dpad_value(),
            ops.pairwise(),
            ops.filter(lambda latest: latest[0].x != latest[1].x and latest[1].x != 0),
            ops.map(
                lambda latest: NavigationIntent(
                    kind=NavigationIntentKind.BROWSE,
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
            ops.map(
                lambda value: 1
                if value >= NAVIGATION_STICK_THRESHOLD
                else (-1 if value <= -NAVIGATION_STICK_THRESHOLD else 0)
            ),
            ops.distinct_until_changed(),
            ops.filter(lambda direction: direction != 0),
            ops.map(
                lambda direction: NavigationIntent(
                    kind=NavigationIntentKind.BROWSE,
                    source="gamepad.left_stick",
                    step=direction,
                )
            ),
        )
        button_south = pipe_in_background(
            self._gamepad.button_tapped(GamepadButton.SOUTH),
            ops.map(
                lambda _button: NavigationIntent(
                    kind=NavigationIntentKind.ACTIVATE,
                    source="gamepad.south",
                )
            ),
        )
        button_north = pipe_in_background(
            self._gamepad.button_tapped(GamepadButton.NORTH),
            ops.map(
                lambda _button: NavigationIntent(
                    kind=NavigationIntentKind.ALTERNATE_ACTIVATE,
                    source="gamepad.north",
                )
            ),
        )
        stream = pipe_in_background(
            reactivex.merge(
                keyboard_left,
                keyboard_right,
                keyboard_down,
                keyboard_up,
                dpad_events,
                stick_events,
                button_south,
                button_north,
            ),
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
            ),
        )

    @cached_property
    def browse(self) -> reactivex.Observable[NavigationIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(lambda intent: intent.kind is NavigationIntentKind.BROWSE),
        )

    @cached_property
    def activate(self) -> reactivex.Observable[NavigationIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(lambda intent: intent.kind is NavigationIntentKind.ACTIVATE),
        )

    @cached_property
    def alternate_activate(self) -> reactivex.Observable[NavigationIntent]:
        return pipe_in_background(
            self.intents,
            ops.filter(
                lambda intent: intent.kind
                is NavigationIntentKind.ALTERNATE_ACTIVATE
            ),
        )

    @cached_property
    def browse_delta(self) -> reactivex.Observable[int]:
        return pipe_in_background(
            self.browse,
            ops.map(lambda intent: intent.step),
        )

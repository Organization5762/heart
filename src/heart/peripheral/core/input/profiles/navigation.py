from __future__ import annotations

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
    def browse_delta(self) -> reactivex.Observable[int]:
        keyboard_left = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_LEFT),
            ops.map(lambda _event: -1),
        )
        keyboard_right = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_RIGHT),
            ops.map(lambda _event: 1),
        )
        dpad_events = pipe_in_background(
            self._gamepad.dpad_value(),
            ops.pairwise(),
            ops.filter(lambda latest: latest[0].x != latest[1].x and latest[1].x != 0),
            ops.map(lambda latest: latest[1].x),
        )
        stick_events = pipe_in_background(
            self._gamepad.axis_value(GamepadAxis.LEFT_X, DEFAULT_GAMEPAD_AXIS_DEAD_ZONE),
            ops.map(
                lambda value: 1 if value >= NAVIGATION_STICK_THRESHOLD else (
                    -1 if value <= -NAVIGATION_STICK_THRESHOLD else 0
                )
            ),
            ops.distinct_until_changed(),
            ops.filter(lambda direction: direction != 0),
        )
        stream = pipe_in_background(
            reactivex.merge(keyboard_left, keyboard_right, dpad_events, stick_events),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.browse_delta",
            source_id="navigation",
            upstream_ids=(
                "keyboard.pressed.left",
                "keyboard.pressed.right",
                "gamepad.dpad",
                "gamepad.axis.left_x",
            ),
        )

    @cached_property
    def activate(self) -> reactivex.Observable[str]:
        keyboard_down = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_DOWN),
            ops.map(lambda _event: "activate"),
        )
        button_south = pipe_in_background(
            self._gamepad.button_tapped(GamepadButton.SOUTH),
            ops.map(lambda _button: "activate"),
        )
        stream = pipe_in_background(reactivex.merge(keyboard_down, button_south))
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.activate",
            source_id="navigation",
            upstream_ids=("keyboard.pressed.down", "gamepad.button_tapped.south"),
        )

    @cached_property
    def alternate_activate(self) -> reactivex.Observable[str]:
        keyboard_up = pipe_in_background(
            self._keyboard.key_pressed(pygame.K_UP),
            ops.map(lambda _event: "alternate_activate"),
        )
        button_north = pipe_in_background(
            self._gamepad.button_tapped(GamepadButton.NORTH),
            ops.map(lambda _button: "alternate_activate"),
        )
        stream = pipe_in_background(reactivex.merge(keyboard_up, button_north))
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="navigation.alternate_activate",
            source_id="navigation",
            upstream_ids=("keyboard.pressed.up", "gamepad.button_tapped.north"),
        )

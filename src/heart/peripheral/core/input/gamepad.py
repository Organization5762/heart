from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from functools import cache, cached_property
from typing import TYPE_CHECKING

import pygame
import reactivex
from reactivex import operators as ops

from heart.peripheral.core.input.debug import (InputDebugStage, InputDebugTap,
                                               instrument_input_stream)
from heart.peripheral.gamepad import Gamepad, GamepadIdentifier
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth,
                                                          DpadType,
                                                          SwitchLikeMapping,
                                                          SwitchProMapping)
from heart.utilities.env import Configuration
from heart.utilities.reactivex_threads import (input_scheduler,
                                               interval_in_background,
                                               pipe_in_background,
                                               pipe_in_main_thread)

if TYPE_CHECKING:
    from heart.peripheral.core.manager import PeripheralManager

GAMEPAD_POLL_INTERVAL_MS = 20
DEFAULT_GAMEPAD_AXIS_DEAD_ZONE = 0.1


class GamepadButton(StrEnum):
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTH = "north"
    PLUS = "plus"
    MINUS = "minus"
    HOME = "home"
    CAPTURE = "capture"
    ZL = "zl"
    ZR = "zr"
    L3 = "l3"
    R3 = "r3"


class GamepadAxis(StrEnum):
    LEFT_X = "left_x"
    LEFT_Y = "left_y"
    RIGHT_X = "right_x"
    RIGHT_Y = "right_y"
    TRIGGER_LEFT = "trigger_left"
    TRIGGER_RIGHT = "trigger_right"


@dataclass(frozen=True, slots=True)
class GamepadStickValue:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class GamepadDpadValue:
    x: int = 0
    y: int = 0


@dataclass(frozen=True, slots=True)
class GamepadButtonTapEvent:
    button: GamepadButton
    timestamp_monotonic: float


@dataclass(frozen=True, slots=True)
class GamepadSnapshot:
    connected: bool
    identifier: str | None
    buttons: dict[GamepadButton, bool] = field(default_factory=dict)
    tapped_buttons: frozenset[GamepadButton] = frozenset()
    axes: dict[GamepadAxis, float] = field(default_factory=dict)
    dpad: GamepadDpadValue = GamepadDpadValue()
    timestamp_monotonic: float = 0.0

    def button_held(self, button: GamepadButton) -> bool:
        return self.buttons.get(button, False)

    def button_tapped(self, button: GamepadButton) -> bool:
        return button in self.tapped_buttons

    def axis_value(
        self,
        axis: GamepadAxis,
        *,
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> float:
        value = self.axes.get(axis, 0.0)
        if abs(value) < dead_zone:
            return 0.0
        return value


class GamepadController:
    def __init__(self, manager: "PeripheralManager", debug_tap: InputDebugTap) -> None:
        self._manager = manager
        self._debug_tap = debug_tap

    @cached_property
    def _snapshot_stream(self) -> reactivex.Observable[GamepadSnapshot]:
        stream = pipe_in_main_thread(
            interval_in_background(
                period=timedelta(milliseconds=GAMEPAD_POLL_INTERVAL_MS),
                scheduler=input_scheduler(),
            ),
            ops.map(lambda _: self._sample()),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="gamepad.snapshot",
            source_id=lambda snapshot: "gamepad" if snapshot.connected else "gamepad:none",
        )

    def snapshot_stream(self) -> reactivex.Observable[GamepadSnapshot]:
        return self._snapshot_stream

    @cache
    def button_held(self, button: GamepadButton) -> reactivex.Observable[bool]:
        stream = pipe_in_background(
            self.snapshot_stream(),
            ops.map(lambda snapshot: snapshot.button_held(button)),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.button_held.{button.value}",
            source_id=button.value,
            upstream_ids=("gamepad.snapshot",),
        )

    @cache
    def button_tapped(
        self,
        button: GamepadButton,
    ) -> reactivex.Observable[GamepadButtonTapEvent]:
        stream = pipe_in_background(
            self.snapshot_stream(),
            ops.filter(lambda snapshot: snapshot.button_tapped(button)),
            ops.map(
                lambda snapshot: GamepadButtonTapEvent(
                    button=button,
                    timestamp_monotonic=snapshot.timestamp_monotonic,
                )
            ),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.button_tapped.{button.value}",
            source_id=button.value,
            upstream_ids=("gamepad.snapshot",),
        )

    @cache
    def axis_value(
        self,
        axis: GamepadAxis,
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> reactivex.Observable[float]:
        stream = pipe_in_background(
            self.snapshot_stream(),
            ops.map(lambda snapshot: snapshot.axis_value(axis, dead_zone=dead_zone)),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.axis.{axis.value}",
            source_id=axis.value,
            upstream_ids=("gamepad.snapshot",),
        )

    @cache
    def stick_value(
        self,
        stick_name: str,
        dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE,
    ) -> reactivex.Observable[GamepadStickValue]:
        axis_x = GamepadAxis.LEFT_X if stick_name == "left" else GamepadAxis.RIGHT_X
        axis_y = GamepadAxis.LEFT_Y if stick_name == "left" else GamepadAxis.RIGHT_Y
        stream = pipe_in_background(
            reactivex.combine_latest(
                self.axis_value(axis_x, dead_zone),
                self.axis_value(axis_y, dead_zone),
            ),
            ops.map(lambda latest: GamepadStickValue(x=latest[0], y=latest[1])),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.stick.{stick_name}",
            source_id=stick_name,
            upstream_ids=(
                f"gamepad.axis.{axis_x.value}",
                f"gamepad.axis.{axis_y.value}",
            ),
        )

    @cache
    def dpad_value(self) -> reactivex.Observable[GamepadDpadValue]:
        stream = pipe_in_background(
            self.snapshot_stream(),
            ops.map(lambda snapshot: snapshot.dpad),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name="gamepad.dpad",
            source_id="dpad",
            upstream_ids=("gamepad.snapshot",),
        )

    def _sample(self) -> GamepadSnapshot:
        gamepad = self._active_gamepad()
        if gamepad is None:
            return GamepadSnapshot(
                connected=False,
                identifier=None,
                timestamp_monotonic=time.monotonic(),
            )

        gamepad.update()
        if not gamepad.is_connected():
            return GamepadSnapshot(
                connected=False,
                identifier=None,
                timestamp_monotonic=time.monotonic(),
            )

        mapping = self._mapping_for_gamepad(gamepad)
        buttons = {
            GamepadButton.SOUTH: gamepad.is_held(mapping.BUTTON_B),
            GamepadButton.EAST: gamepad.is_held(mapping.BUTTON_A),
            GamepadButton.WEST: gamepad.is_held(mapping.BUTTON_Y),
            GamepadButton.NORTH: gamepad.is_held(mapping.BUTTON_X),
            GamepadButton.PLUS: gamepad.is_held(mapping.BUTTON_PLUS),
            GamepadButton.MINUS: gamepad.is_held(mapping.BUTTON_MINUS),
            GamepadButton.HOME: gamepad.is_held(mapping.BUTTON_HOME),
            GamepadButton.CAPTURE: mapping.BUTTON_CAPTURE >= 0 and gamepad.is_held(mapping.BUTTON_CAPTURE),
            GamepadButton.ZL: gamepad.is_held(mapping.BUTTON_ZL),
            GamepadButton.ZR: gamepad.is_held(mapping.BUTTON_ZR),
            GamepadButton.L3: gamepad.is_held(mapping.BUTTON_L3),
            GamepadButton.R3: gamepad.is_held(mapping.BUTTON_R3),
        }
        tapped_buttons = frozenset(
            button
            for button, button_id in {
                GamepadButton.SOUTH: mapping.BUTTON_B,
                GamepadButton.EAST: mapping.BUTTON_A,
                GamepadButton.WEST: mapping.BUTTON_Y,
                GamepadButton.NORTH: mapping.BUTTON_X,
                GamepadButton.PLUS: mapping.BUTTON_PLUS,
                GamepadButton.MINUS: mapping.BUTTON_MINUS,
                GamepadButton.HOME: mapping.BUTTON_HOME,
                GamepadButton.CAPTURE: mapping.BUTTON_CAPTURE,
                GamepadButton.ZL: mapping.BUTTON_ZL,
                GamepadButton.ZR: mapping.BUTTON_ZR,
                GamepadButton.L3: mapping.BUTTON_L3,
                GamepadButton.R3: mapping.BUTTON_R3,
            }.items()
            if button_id >= 0 and gamepad.was_tapped(button_id)
        )
        axes = {
            GamepadAxis.LEFT_X: gamepad.axis_value(mapping.AXIS_LEFT_X, dead_zone=0.0),
            GamepadAxis.LEFT_Y: gamepad.axis_value(mapping.AXIS_LEFT_Y, dead_zone=0.0),
            GamepadAxis.RIGHT_X: gamepad.axis_value(mapping.AXIS_RIGHT_X, dead_zone=0.0),
            GamepadAxis.RIGHT_Y: gamepad.axis_value(mapping.AXIS_RIGHT_Y, dead_zone=0.0),
            GamepadAxis.TRIGGER_LEFT: gamepad.axis_value(mapping.AXIS_L, dead_zone=0.0),
            GamepadAxis.TRIGGER_RIGHT: gamepad.axis_value(mapping.AXIS_R, dead_zone=0.0),
        }
        dpad = self._read_dpad(gamepad, mapping)
        return GamepadSnapshot(
            connected=True,
            identifier=gamepad.gamepad_identifier.value,
            buttons=buttons,
            tapped_buttons=tapped_buttons,
            axes=axes,
            dpad=dpad,
            timestamp_monotonic=time.monotonic(),
        )

    def _active_gamepad(self) -> Gamepad | None:
        for peripheral in self._manager.peripherals:
            if isinstance(peripheral, Gamepad):
                return peripheral
        return None

    @staticmethod
    def _mapping_for_gamepad(gamepad: Gamepad) -> SwitchLikeMapping:
        identifier = gamepad.gamepad_identifier
        if identifier is GamepadIdentifier.SWITCH_PRO:
            return SwitchProMapping()
        if Configuration.is_pi():
            return BitDoLite2Bluetooth()
        return BitDoLite2()

    @staticmethod
    def _read_dpad(
        gamepad: Gamepad,
        mapping: SwitchLikeMapping,
    ) -> GamepadDpadValue:
        if mapping.get_dpad_type() is DpadType.HAT and gamepad.joystick is not None:
            hat_index = mapping.DPAD_HAT
            if hat_index is None or hat_index < 0:
                return GamepadDpadValue()
            try:
                x_dir, y_dir = gamepad.joystick.get_hat(hat_index)
            except pygame.error:
                return GamepadDpadValue()
            return GamepadDpadValue(x=int(x_dir), y=int(y_dir))

        if mapping.get_dpad_type() is DpadType.BUTTONS:
            x_dir = int(gamepad.is_held(mapping.DPAD_RIGHT)) - int(
                gamepad.is_held(mapping.DPAD_LEFT)
            )
            y_dir = int(gamepad.is_held(mapping.DPAD_UP)) - int(
                gamepad.is_held(mapping.DPAD_DOWN)
            )
            return GamepadDpadValue(x=x_dir, y=y_dir)

        return GamepadDpadValue()

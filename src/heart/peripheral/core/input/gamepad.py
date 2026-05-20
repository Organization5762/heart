from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import timedelta
from enum import StrEnum
from functools import cache, cached_property
from typing import TYPE_CHECKING

import pygame
from manyfold import StreamNode, Timer

from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.streams import combine_latest
from heart.peripheral.gamepad import Gamepad, GamepadIdentifier
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth,
                                                          DpadType,
                                                          SwitchLikeMapping,
                                                          SwitchProMapping)
from heart.utilities.env import Configuration

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
        self, axis: GamepadAxis, *, dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
    ) -> float:
        value = self.axes.get(axis, 0.0)
        if abs(value) < dead_zone:
            return 0.0
        return value


class GamepadController:
    def __init__(self, manager: "PeripheralManager", debug_tap: InputDebugTap) -> None:
        self._manager = manager
        self._debug_tap = debug_tap
        self._snapshot_streams_by_joystick_id: dict[
            int, StreamNode[GamepadSnapshot]
        ] = {}

    @cached_property
    def _snapshot_stream(self) -> StreamNode[GamepadSnapshot]:
        stream = (
            Timer(period=timedelta(milliseconds=GAMEPAD_POLL_INTERVAL_MS))
            .then_on_main_thread()
            .map(lambda _: self._sample(include_tapped_buttons=False))
            .distinct_until_changed()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.RAW,
            stream_name="gamepad.snapshot",
            source_id=lambda snapshot: (
                "gamepad" if snapshot.connected else "gamepad:none"
            ),
        ).connect(stream)

    def snapshot_stream(
        self,
        joystick_id: int | None = None,
    ) -> StreamNode[GamepadSnapshot]:
        if joystick_id is not None:
            return self._snapshot_stream_for_joystick_id(joystick_id)
        return self._snapshot_stream

    def _snapshot_stream_for_joystick_id(
        self,
        joystick_id: int,
    ) -> StreamNode[GamepadSnapshot]:
        if joystick_id not in self._snapshot_streams_by_joystick_id:
            stream = (
                Timer(period=timedelta(milliseconds=GAMEPAD_POLL_INTERVAL_MS))
                .then_on_main_thread()
                .map(
                    lambda _: self._sample(
                        joystick_id=joystick_id,
                        include_tapped_buttons=False,
                    )
                )
                .distinct_until_changed()
            )
            self._snapshot_streams_by_joystick_id[joystick_id] = InputDebugNode(
                tap=self._debug_tap,
                stage=InputDebugStage.RAW,
                stream_name=f"gamepad.snapshot.{joystick_id}",
                source_id=lambda snapshot: (
                    f"gamepad:{joystick_id}"
                    if snapshot.connected
                    else f"gamepad:{joystick_id}:none"
                ),
            ).connect(stream)
        return self._snapshot_streams_by_joystick_id[joystick_id]

    @cache
    def button_held(self, button: GamepadButton) -> StreamNode[bool]:
        stream = (
            self.snapshot_stream()
            .map(lambda snapshot: snapshot.button_held(button))
            .distinct_until_changed()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.button_held.{button.value}",
            source_id=button.value,
            upstream_ids=("gamepad.snapshot",),
        ).connect(stream)

    @cache
    def button_tapped(self, button: GamepadButton) -> StreamNode[GamepadButtonTapEvent]:
        stream = (
            self.snapshot_stream()
            .pairwise()
            .filter(
                lambda latest: not latest[0].button_held(button)
                and latest[1].button_held(button)
            )
            .map(
                lambda latest: GamepadButtonTapEvent(
                    button=button, timestamp_monotonic=latest[1].timestamp_monotonic
                )
            )
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.button_tapped.{button.value}",
            source_id=button.value,
            upstream_ids=("gamepad.snapshot",),
        ).connect(stream)

    @cache
    def axis_value(
        self, axis: GamepadAxis, dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
    ) -> StreamNode[float]:
        stream = (
            self.snapshot_stream()
            .map(lambda snapshot: snapshot.axis_value(axis, dead_zone=dead_zone))
            .distinct_until_changed()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.axis.{axis.value}",
            source_id=axis.value,
            upstream_ids=("gamepad.snapshot",),
        ).connect(stream)

    @cache
    def stick_value(
        self, stick_name: str, dead_zone: float = DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
    ) -> StreamNode[GamepadStickValue]:
        axis_x = GamepadAxis.LEFT_X if stick_name == "left" else GamepadAxis.RIGHT_X
        axis_y = GamepadAxis.LEFT_Y if stick_name == "left" else GamepadAxis.RIGHT_Y
        stream = (
            combine_latest(
                self.axis_value(axis_x, dead_zone),
                self.axis_value(axis_y, dead_zone),
            )
            .map(lambda latest: GamepadStickValue(x=latest[0], y=latest[1]))
            .distinct_until_changed()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name=f"gamepad.stick.{stick_name}",
            source_id=stick_name,
            upstream_ids=(
                f"gamepad.axis.{axis_x.value}",
                f"gamepad.axis.{axis_y.value}",
            ),
        ).connect(stream)

    @cache
    def dpad_value(self) -> StreamNode[GamepadDpadValue]:
        stream = (
            self.snapshot_stream()
            .map(lambda snapshot: snapshot.dpad)
            .distinct_until_changed()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.VIEW,
            stream_name="gamepad.dpad",
            source_id="dpad",
            upstream_ids=("gamepad.snapshot",),
        ).connect(stream)

    def sample(
        self,
        joystick_id: int | None = None,
        *,
        include_tapped_buttons: bool = True,
    ) -> GamepadSnapshot:
        return self._sample(
            joystick_id=joystick_id,
            include_tapped_buttons=include_tapped_buttons,
        )

    def _sample(
        self,
        joystick_id: int | None = None,
        *,
        include_tapped_buttons: bool = True,
    ) -> GamepadSnapshot:
        self._pump_gamepad_events()
        if joystick_id is not None:
            gamepad = self._gamepad(joystick_id)
            if gamepad is None:
                return GamepadSnapshot(
                    connected=False,
                    identifier=None,
                    timestamp_monotonic=time.monotonic(),
                )
            return self._sample_gamepad(
                gamepad,
                include_tapped_buttons=include_tapped_buttons,
            )
        snapshots = [
            snapshot
            for gamepad in self._gamepads()
            if (
                snapshot := self._sample_gamepad(
                    gamepad,
                    include_tapped_buttons=include_tapped_buttons,
                )
            ).connected
        ]
        if not snapshots:
            return GamepadSnapshot(
                connected=False, identifier=None, timestamp_monotonic=time.monotonic()
            )
        return self._combine_snapshots(snapshots)

    def _sample_gamepad(
        self,
        gamepad: Gamepad,
        *,
        include_tapped_buttons: bool = True,
    ) -> GamepadSnapshot:
        gamepad.update(pump_events=False)
        if not gamepad.is_connected():
            return GamepadSnapshot(
                connected=False, identifier=None, timestamp_monotonic=time.monotonic()
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
            GamepadButton.CAPTURE: mapping.BUTTON_CAPTURE >= 0
            and gamepad.is_held(mapping.BUTTON_CAPTURE),
            GamepadButton.ZL: gamepad.is_held(mapping.BUTTON_ZL),
            GamepadButton.ZR: gamepad.is_held(mapping.BUTTON_ZR),
            GamepadButton.L3: gamepad.is_held(mapping.BUTTON_L3),
            GamepadButton.R3: gamepad.is_held(mapping.BUTTON_R3),
        }
        tapped_buttons = frozenset()
        if include_tapped_buttons:
            tapped_buttons = frozenset(
                (
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
            )
        axes = {
            GamepadAxis.LEFT_X: gamepad.axis_value(mapping.AXIS_LEFT_X, dead_zone=0.0),
            GamepadAxis.LEFT_Y: gamepad.axis_value(mapping.AXIS_LEFT_Y, dead_zone=0.0),
            GamepadAxis.RIGHT_X: gamepad.axis_value(
                mapping.AXIS_RIGHT_X, dead_zone=0.0
            ),
            GamepadAxis.RIGHT_Y: gamepad.axis_value(
                mapping.AXIS_RIGHT_Y, dead_zone=0.0
            ),
            GamepadAxis.TRIGGER_LEFT: gamepad.axis_value(mapping.AXIS_L, dead_zone=0.0),
            GamepadAxis.TRIGGER_RIGHT: gamepad.axis_value(
                mapping.AXIS_R, dead_zone=0.0
            ),
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

    def _gamepads(self) -> tuple[Gamepad, ...]:
        gamepads: list[Gamepad] = []
        for peripheral in self._manager.peripherals:
            if isinstance(peripheral, Gamepad):
                gamepads.append(peripheral)
        return tuple(gamepads)

    def _gamepad(self, joystick_id: int) -> Gamepad | None:
        for gamepad in self._gamepads():
            if gamepad.joystick_id == joystick_id:
                return gamepad
        return None

    @staticmethod
    def _pump_gamepad_events() -> None:
        try:
            pygame.event.pump()
        except pygame.error:
            return

    def _combine_snapshots(
        self,
        snapshots: list[GamepadSnapshot],
    ) -> GamepadSnapshot:
        return GamepadSnapshot(
            connected=True,
            identifier="+".join(
                snapshot.identifier or "unknown" for snapshot in snapshots
            ),
            buttons=self._combine_buttons(snapshots),
            tapped_buttons=frozenset().union(
                *(snapshot.tapped_buttons for snapshot in snapshots)
            ),
            axes=self._combine_axes(snapshots),
            dpad=self._combine_dpad(snapshots),
            timestamp_monotonic=max(
                snapshot.timestamp_monotonic for snapshot in snapshots
            ),
        )

    @staticmethod
    def _combine_buttons(
        snapshots: list[GamepadSnapshot],
    ) -> dict[GamepadButton, bool]:
        return {
            button: any(snapshot.button_held(button) for snapshot in snapshots)
            for button in GamepadButton
        }

    @staticmethod
    def _combine_axes(
        snapshots: list[GamepadSnapshot],
    ) -> dict[GamepadAxis, float]:
        axes: dict[GamepadAxis, float] = {}
        for axis in GamepadAxis:
            values = [snapshot.axes.get(axis, 0.0) for snapshot in snapshots]
            if axis in {GamepadAxis.TRIGGER_LEFT, GamepadAxis.TRIGGER_RIGHT}:
                axes[axis] = max(values)
            else:
                axes[axis] = max(values, key=abs)
        return axes

    @staticmethod
    def _combine_dpad(snapshots: list[GamepadSnapshot]) -> GamepadDpadValue:
        x = max(-1, min(1, sum(snapshot.dpad.x for snapshot in snapshots)))
        y = max(-1, min(1, sum(snapshot.dpad.y for snapshot in snapshots)))
        return GamepadDpadValue(x=x, y=y)

    @staticmethod
    def _mapping_for_gamepad(gamepad: Gamepad) -> SwitchLikeMapping:
        identifier = gamepad.gamepad_identifier
        if identifier is GamepadIdentifier.SWITCH_PRO:
            return SwitchProMapping()
        if Configuration.is_pi():
            return BitDoLite2Bluetooth()
        return BitDoLite2()

    @staticmethod
    def _read_dpad(gamepad: Gamepad, mapping: SwitchLikeMapping) -> GamepadDpadValue:
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

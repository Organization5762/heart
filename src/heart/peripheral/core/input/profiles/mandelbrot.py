from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import pygame
from manyfold import MergeNode, StreamNode

from heart.peripheral.core.input.debug import (InputDebugNode, InputDebugStage,
                                               InputDebugTap)
from heart.peripheral.core.input.gamepad import (
    DEFAULT_GAMEPAD_AXIS_DEAD_ZONE, GamepadAxis, GamepadButton,
    GamepadController, GamepadSnapshot)
from heart.peripheral.core.input.keyboard import (KeyboardController,
                                                  KeyboardSnapshot)
from heart.peripheral.core.input.streams import map_stream
from heart.peripheral.core.streams import combine_latest

MANDELBROT_RIGHT_STICK_DEAD_ZONE = 0.35


@dataclass(frozen=True, slots=True)
class MandelbrotEdgeState:
    next_view_mode_revision: int = 0
    previous_view_mode_revision: int = 0
    toggle_debug_revision: int = 0
    toggle_fps_revision: int = 0
    toggle_orientation_revision: int = 0
    orientation_kind: str | None = None
    toggle_auto_mode_revision: int = 0
    palette_revision: int = 0
    palette_delta: int = 0


@dataclass(frozen=True, slots=True)
class MandelbrotMotionState:
    move_x: float = 0.0
    move_y: float = 0.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    move_multiplier: float = 1.0
    home_modifier: bool = False
    plus_held: bool = False
    minus_held: bool = False
    zoom_in: bool = False
    zoom_out: bool = False
    increase_iterations: bool = False
    decrease_iterations: bool = False


@dataclass(frozen=True, slots=True)
class MandelbrotControlState:
    move_x: float = 0.0
    move_y: float = 0.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    move_multiplier: float = 1.0
    home_modifier: bool = False
    plus_held: bool = False
    minus_held: bool = False
    zoom_in: bool = False
    zoom_out: bool = False
    increase_iterations: bool = False
    decrease_iterations: bool = False
    next_view_mode_revision: int = 0
    previous_view_mode_revision: int = 0
    toggle_debug_revision: int = 0
    toggle_fps_revision: int = 0
    toggle_orientation_revision: int = 0
    orientation_kind: str | None = None
    toggle_auto_mode_revision: int = 0
    palette_revision: int = 0
    palette_delta: int = 0


@dataclass(frozen=True, slots=True)
class _MandelbrotCommand:
    source: str


@dataclass(frozen=True, slots=True)
class NextViewModeCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class PreviousViewModeCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class ToggleDebugCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class ToggleFpsCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class SetOrientationCommand(_MandelbrotCommand):
    orientation_kind: str


@dataclass(frozen=True, slots=True)
class ToggleOrientationCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class ToggleAutoModeCommand(_MandelbrotCommand):
    pass


@dataclass(frozen=True, slots=True)
class CyclePaletteCommand(_MandelbrotCommand):
    palette_delta: int


MandelbrotCommand = (
    NextViewModeCommand
    | PreviousViewModeCommand
    | ToggleDebugCommand
    | ToggleFpsCommand
    | SetOrientationCommand
    | ToggleOrientationCommand
    | ToggleAutoModeCommand
    | CyclePaletteCommand
)


class MandelbrotControlProfile:
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
    def motion_state(self) -> StreamNode[MandelbrotMotionState]:
        stream = (
            combine_latest(
                self._keyboard.snapshot_stream().start_with(
                    KeyboardSnapshot(pressed_keys=frozenset(), timestamp_ms=0.0)
                ),
                self._gamepad.snapshot_stream().start_with(
                    GamepadSnapshot(connected=False, identifier=None)
                ),
            )
            .map(lambda latest: self._to_motion_state_from_snapshots(*latest))
            .distinct_until_changed()

        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.motion_state",
            source_id="mandelbrot.motion",
            upstream_ids=("keyboard", "gamepad"),
        ).connect(stream)

    @cached_property
    def command_events(self) -> StreamNode[MandelbrotCommand]:
        stream = MergeNode.merge(
            self._keyboard_command_streams(), self._gamepad_command_streams()
        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.command",
            source_id=lambda command: command.source,
            upstream_ids=("keyboard", "gamepad"),
        ).connect(stream)

    @cached_property
    def _edge_state(self) -> StreamNode[MandelbrotEdgeState]:
        return (
            self.command_events.scan(self._apply_command, seed=MandelbrotEdgeState())
            .start_with(MandelbrotEdgeState())

        )

    @cached_property
    def _observable(self) -> StreamNode[MandelbrotControlState]:
        stream = (
            combine_latest(self.motion_state, self._edge_state)
            .map(lambda latest: self._to_compatibility_state(*latest))
            .distinct_until_changed()

        )
        return InputDebugNode(
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.controls",
            source_id="mandelbrot",
            upstream_ids=("mandelbrot.motion_state", "mandelbrot.command"),
        ).connect(stream)

    def observable(self) -> StreamNode[MandelbrotControlState]:
        return self._observable

    def _keyboard_command_streams(self) -> StreamNode[MandelbrotCommand]:
        return MergeNode.merge(
            map_stream(
                self._keyboard.key_pressed(pygame.K_LEFTBRACKET),
                lambda _event: PreviousViewModeCommand(source="keyboard.left_bracket"),
            ),
            map_stream(
                self._keyboard.key_pressed(pygame.K_RIGHTBRACKET),
                lambda _event: NextViewModeCommand(source="keyboard.right_bracket"),
            ),
            map_stream(
                self._keyboard.key_pressed(pygame.K_i),
                lambda _event: ToggleDebugCommand(source="keyboard.i"),
            ),
            map_stream(
                self._keyboard.key_pressed(pygame.K_p),
                lambda _event: ToggleFpsCommand(source="keyboard.p"),
            ),
            map_stream(
                self._keyboard.key_pressed(pygame.K_0),
                lambda _event: SetOrientationCommand(
                    source="keyboard.0", orientation_kind="rectangle"
                ),
            ),
            map_stream(
                self._keyboard.key_pressed(pygame.K_9),
                lambda _event: SetOrientationCommand(
                    source="keyboard.9", orientation_kind="cube"
                ),
            ),
        )

    def _gamepad_command_streams(self) -> StreamNode[MandelbrotCommand]:
        return MergeNode.merge(
            map_stream(
                self._gamepad.button_tapped(GamepadButton.ZR),
                lambda _button: NextViewModeCommand(source="gamepad.zr"),
            ),
            map_stream(
                self._gamepad.button_tapped(GamepadButton.ZL),
                lambda _button: PreviousViewModeCommand(source="gamepad.zl"),
            ),
            map_stream(
                self._gamepad.button_tapped(GamepadButton.HOME),
                lambda _button: ToggleAutoModeCommand(source="gamepad.home"),
            ),
            map_stream(
                self._gamepad.button_tapped(GamepadButton.NORTH),
                lambda _button: CyclePaletteCommand(
                    source="gamepad.north", palette_delta=1
                ),
            ),
            map_stream(
                self._gamepad.button_tapped(GamepadButton.WEST),
                lambda _button: CyclePaletteCommand(
                    source="gamepad.west", palette_delta=-1
                ),
            ),
            self._combo_command(
                GamepadButton.HOME,
                GamepadButton.PLUS,
                ToggleOrientationCommand(source="gamepad.home_plus"),
            ),
            self._combo_command(
                GamepadButton.HOME,
                GamepadButton.MINUS,
                ToggleFpsCommand(source="gamepad.home_minus"),
            ),
        )

    def _combo_command(
        self,
        modifier: GamepadButton,
        primary: GamepadButton,
        command: MandelbrotCommand,
    ) -> StreamNode[MandelbrotCommand]:
        return (
            combine_latest(
                self._gamepad.button_held(modifier),
                self._gamepad.button_held(primary),
            )
            .map(lambda latest: bool(latest[0]) and bool(latest[1]))
            .distinct_until_changed()
            .filter(bool)
            .map(lambda _active: command)

        )

    def _apply_command(
        self, state: MandelbrotEdgeState, command: MandelbrotCommand
    ) -> MandelbrotEdgeState:
        if isinstance(command, NextViewModeCommand):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision + 1,
                previous_view_mode_revision=state.previous_view_mode_revision,
                toggle_debug_revision=state.toggle_debug_revision,
                toggle_fps_revision=state.toggle_fps_revision,
                toggle_orientation_revision=state.toggle_orientation_revision,
                orientation_kind=state.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        if isinstance(command, PreviousViewModeCommand):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision,
                previous_view_mode_revision=state.previous_view_mode_revision + 1,
                toggle_debug_revision=state.toggle_debug_revision,
                toggle_fps_revision=state.toggle_fps_revision,
                toggle_orientation_revision=state.toggle_orientation_revision,
                orientation_kind=state.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        if isinstance(command, ToggleDebugCommand):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision,
                previous_view_mode_revision=state.previous_view_mode_revision,
                toggle_debug_revision=state.toggle_debug_revision + 1,
                toggle_fps_revision=state.toggle_fps_revision,
                toggle_orientation_revision=state.toggle_orientation_revision,
                orientation_kind=state.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        if isinstance(command, ToggleFpsCommand):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision,
                previous_view_mode_revision=state.previous_view_mode_revision,
                toggle_debug_revision=state.toggle_debug_revision,
                toggle_fps_revision=state.toggle_fps_revision + 1,
                toggle_orientation_revision=state.toggle_orientation_revision,
                orientation_kind=state.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        if isinstance(command, (SetOrientationCommand, ToggleOrientationCommand)):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision,
                previous_view_mode_revision=state.previous_view_mode_revision,
                toggle_debug_revision=state.toggle_debug_revision,
                toggle_fps_revision=state.toggle_fps_revision,
                toggle_orientation_revision=state.toggle_orientation_revision + 1,
                orientation_kind=command.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        if isinstance(command, ToggleAutoModeCommand):
            return MandelbrotEdgeState(
                next_view_mode_revision=state.next_view_mode_revision,
                previous_view_mode_revision=state.previous_view_mode_revision,
                toggle_debug_revision=state.toggle_debug_revision,
                toggle_fps_revision=state.toggle_fps_revision,
                toggle_orientation_revision=state.toggle_orientation_revision,
                orientation_kind=state.orientation_kind,
                toggle_auto_mode_revision=state.toggle_auto_mode_revision + 1,
                palette_revision=state.palette_revision,
                palette_delta=state.palette_delta,
            )
        assert isinstance(command, CyclePaletteCommand)
        return MandelbrotEdgeState(
            next_view_mode_revision=state.next_view_mode_revision,
            previous_view_mode_revision=state.previous_view_mode_revision,
            toggle_debug_revision=state.toggle_debug_revision,
            toggle_fps_revision=state.toggle_fps_revision,
            toggle_orientation_revision=state.toggle_orientation_revision,
            orientation_kind=state.orientation_kind,
            toggle_auto_mode_revision=state.toggle_auto_mode_revision,
            palette_revision=state.palette_revision + 1,
            palette_delta=command.palette_delta,
        )

    def _to_motion_state_from_snapshots(
        self, keyboard_snapshot: KeyboardSnapshot, gamepad_snapshot: GamepadSnapshot
    ) -> MandelbrotMotionState:
        pressed_keys = keyboard_snapshot.pressed_keys
        keyboard_move_x = float(pygame.K_d in pressed_keys) - float(
            pygame.K_a in pressed_keys
        )
        keyboard_move_y = float(pygame.K_s in pressed_keys) - float(
            pygame.K_w in pressed_keys
        )
        trigger_right = gamepad_snapshot.axis_value(
            GamepadAxis.TRIGGER_RIGHT, dead_zone=0.0
        )
        trigger_left = gamepad_snapshot.axis_value(
            GamepadAxis.TRIGGER_LEFT, dead_zone=0.0
        )
        left_stick_x = gamepad_snapshot.axis_value(
            GamepadAxis.LEFT_X, dead_zone=DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
        )
        left_stick_y = gamepad_snapshot.axis_value(
            GamepadAxis.LEFT_Y, dead_zone=DEFAULT_GAMEPAD_AXIS_DEAD_ZONE
        )
        right_stick_x = gamepad_snapshot.axis_value(
            GamepadAxis.RIGHT_X, dead_zone=MANDELBROT_RIGHT_STICK_DEAD_ZONE
        )
        right_stick_y = gamepad_snapshot.axis_value(
            GamepadAxis.RIGHT_Y, dead_zone=MANDELBROT_RIGHT_STICK_DEAD_ZONE
        )
        button_b_held = gamepad_snapshot.button_held(GamepadButton.EAST)
        button_home_held = gamepad_snapshot.button_held(GamepadButton.HOME)
        button_plus_held = gamepad_snapshot.button_held(GamepadButton.PLUS)
        button_minus_held = gamepad_snapshot.button_held(GamepadButton.MINUS)
        dpad = gamepad_snapshot.dpad
        zoom_in = pygame.K_e in pressed_keys or trigger_right > 0.0
        zoom_out = pygame.K_q in pressed_keys or trigger_left > 0.0
        increase_iterations = pygame.K_j in pressed_keys or (
            not button_home_held and bool(button_plus_held)
        )
        decrease_iterations = pygame.K_k in pressed_keys or (
            not button_home_held and bool(button_minus_held)
        )
        move_multiplier = 2.0 if button_b_held else 1.0
        return MandelbrotMotionState(
            move_x=keyboard_move_x + dpad.x + left_stick_x,
            move_y=keyboard_move_y - dpad.y + left_stick_y,
            pan_x=right_stick_x,
            pan_y=-right_stick_y,
            move_multiplier=move_multiplier,
            home_modifier=bool(button_home_held),
            plus_held=bool(button_plus_held),
            minus_held=bool(button_minus_held),
            zoom_in=zoom_in,
            zoom_out=zoom_out,
            increase_iterations=increase_iterations,
            decrease_iterations=decrease_iterations,
        )

    def _to_compatibility_state(
        self, motion_state: MandelbrotMotionState, edge_state: MandelbrotEdgeState
    ) -> MandelbrotControlState:
        return MandelbrotControlState(
            move_x=motion_state.move_x,
            move_y=motion_state.move_y,
            pan_x=motion_state.pan_x,
            pan_y=motion_state.pan_y,
            move_multiplier=motion_state.move_multiplier,
            home_modifier=motion_state.home_modifier,
            plus_held=motion_state.plus_held,
            minus_held=motion_state.minus_held,
            zoom_in=motion_state.zoom_in,
            zoom_out=motion_state.zoom_out,
            increase_iterations=motion_state.increase_iterations,
            decrease_iterations=motion_state.decrease_iterations,
            next_view_mode_revision=edge_state.next_view_mode_revision,
            previous_view_mode_revision=edge_state.previous_view_mode_revision,
            toggle_debug_revision=edge_state.toggle_debug_revision,
            toggle_fps_revision=edge_state.toggle_fps_revision,
            toggle_orientation_revision=edge_state.toggle_orientation_revision,
            orientation_kind=edge_state.orientation_kind,
            toggle_auto_mode_revision=edge_state.toggle_auto_mode_revision,
            palette_revision=edge_state.palette_revision,
            palette_delta=edge_state.palette_delta,
        )

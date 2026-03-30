from __future__ import annotations

from dataclasses import dataclass
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
    def motion_state(self) -> reactivex.Observable[MandelbrotMotionState]:
        keyboard_state = reactivex.combine_latest(
            self._keyboard.key_state(pygame.K_w),
            self._keyboard.key_state(pygame.K_s),
            self._keyboard.key_state(pygame.K_a),
            self._keyboard.key_state(pygame.K_d),
            self._keyboard.key_state(pygame.K_q),
            self._keyboard.key_state(pygame.K_e),
            self._keyboard.key_state(pygame.K_j),
            self._keyboard.key_state(pygame.K_k),
        )
        gamepad_state = reactivex.combine_latest(
            self._gamepad.button_held(GamepadButton.EAST),
            self._gamepad.button_held(GamepadButton.HOME),
            self._gamepad.button_held(GamepadButton.PLUS),
            self._gamepad.button_held(GamepadButton.MINUS),
            self._gamepad.axis_value(GamepadAxis.TRIGGER_RIGHT, 0.0),
            self._gamepad.axis_value(GamepadAxis.TRIGGER_LEFT, 0.0),
            self._gamepad.stick_value("left", DEFAULT_GAMEPAD_AXIS_DEAD_ZONE),
            self._gamepad.stick_value("right", MANDELBROT_RIGHT_STICK_DEAD_ZONE),
        )

        stream = pipe_in_background(
            reactivex.combine_latest(keyboard_state, gamepad_state),
            ops.map(lambda latest: self._to_motion_state(*latest)),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.motion_state",
            source_id="mandelbrot.motion",
            upstream_ids=("keyboard", "gamepad"),
        )

    @cached_property
    def command_events(self) -> reactivex.Observable[MandelbrotCommand]:
        stream = pipe_in_background(
            reactivex.merge(
                self._keyboard_command_streams(),
                self._gamepad_command_streams(),
            ),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.command",
            source_id=lambda command: command.source,
            upstream_ids=("keyboard", "gamepad"),
        )

    @cached_property
    def _edge_state(self) -> reactivex.Observable[MandelbrotEdgeState]:
        return pipe_in_background(
            self.command_events,
            ops.scan(self._apply_command, seed=MandelbrotEdgeState()),
            ops.start_with(MandelbrotEdgeState()),
        )

    @cached_property
    def _observable(self) -> reactivex.Observable[MandelbrotControlState]:
        stream = pipe_in_background(
            reactivex.combine_latest(self.motion_state, self._edge_state),
            ops.map(lambda latest: self._to_compatibility_state(*latest)),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.controls",
            source_id="mandelbrot",
            upstream_ids=("mandelbrot.motion_state", "mandelbrot.command"),
        )

    def observable(self) -> reactivex.Observable[MandelbrotControlState]:
        return self._observable

    def _keyboard_command_streams(self) -> reactivex.Observable[MandelbrotCommand]:
        return reactivex.merge(
            self._keyboard.key_pressed(pygame.K_LEFTBRACKET).pipe(
                ops.map(
                    lambda _event: PreviousViewModeCommand(
                        source="keyboard.left_bracket",
                    )
                )
            ),
            self._keyboard.key_pressed(pygame.K_RIGHTBRACKET).pipe(
                ops.map(
                    lambda _event: NextViewModeCommand(
                        source="keyboard.right_bracket",
                    )
                )
            ),
            self._keyboard.key_pressed(pygame.K_i).pipe(
                ops.map(
                    lambda _event: ToggleDebugCommand(
                        source="keyboard.i",
                    )
                )
            ),
            self._keyboard.key_pressed(pygame.K_p).pipe(
                ops.map(
                    lambda _event: ToggleFpsCommand(
                        source="keyboard.p",
                    )
                )
            ),
            self._keyboard.key_pressed(pygame.K_0).pipe(
                ops.map(
                    lambda _event: SetOrientationCommand(
                        source="keyboard.0",
                        orientation_kind="rectangle",
                    )
                )
            ),
            self._keyboard.key_pressed(pygame.K_9).pipe(
                ops.map(
                    lambda _event: SetOrientationCommand(
                        source="keyboard.9",
                        orientation_kind="cube",
                    )
                )
            ),
        )

    def _gamepad_command_streams(self) -> reactivex.Observable[MandelbrotCommand]:
        return reactivex.merge(
            self._gamepad.button_tapped(GamepadButton.ZR).pipe(
                ops.map(
                    lambda _button: NextViewModeCommand(
                        source="gamepad.zr",
                    )
                )
            ),
            self._gamepad.button_tapped(GamepadButton.ZL).pipe(
                ops.map(
                    lambda _button: PreviousViewModeCommand(
                        source="gamepad.zl",
                    )
                )
            ),
            self._gamepad.button_tapped(GamepadButton.HOME).pipe(
                ops.map(
                    lambda _button: ToggleAutoModeCommand(
                        source="gamepad.home",
                    )
                )
            ),
            self._gamepad.button_tapped(GamepadButton.NORTH).pipe(
                ops.map(
                    lambda _button: CyclePaletteCommand(
                        source="gamepad.north",
                        palette_delta=1,
                    )
                )
            ),
            self._gamepad.button_tapped(GamepadButton.WEST).pipe(
                ops.map(
                    lambda _button: CyclePaletteCommand(
                        source="gamepad.west",
                        palette_delta=-1,
                    )
                )
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
    ) -> reactivex.Observable[MandelbrotCommand]:
        return pipe_in_background(
            reactivex.combine_latest(
                self._gamepad.button_held(modifier),
                self._gamepad.button_held(primary),
            ),
            ops.map(lambda latest: bool(latest[0]) and bool(latest[1])),
            ops.distinct_until_changed(),
            ops.filter(bool),
            ops.map(lambda _active: command),
        )

    def _apply_command(
        self,
        state: MandelbrotEdgeState,
        command: MandelbrotCommand,
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

    def _to_motion_state(
        self,
        keyboard_state: tuple[object, ...],
        gamepad_state: tuple[object, ...],
    ) -> MandelbrotMotionState:
        (
            key_w,
            key_s,
            key_a,
            key_d,
            key_q,
            key_e,
            key_j,
            key_k,
        ) = keyboard_state
        (
            button_b_held,
            button_home_held,
            button_plus_held,
            button_minus_held,
            trigger_right,
            trigger_left,
            left_stick,
            right_stick,
        ) = gamepad_state

        keyboard_move_x = float(key_d.pressed) - float(key_a.pressed)
        keyboard_move_y = float(key_s.pressed) - float(key_w.pressed)
        zoom_in = bool(key_e.pressed) or trigger_right > 0.0
        zoom_out = bool(key_q.pressed) or trigger_left > 0.0
        increase_iterations = bool(key_j.pressed) or (
            not button_home_held and bool(button_plus_held)
        )
        decrease_iterations = bool(key_k.pressed) or (
            not button_home_held and bool(button_minus_held)
        )
        move_multiplier = 2.0 if button_b_held else 1.0

        return MandelbrotMotionState(
            move_x=keyboard_move_x + left_stick.x,
            move_y=keyboard_move_y - left_stick.y,
            pan_x=right_stick.x,
            pan_y=-right_stick.y,
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
        self,
        motion_state: MandelbrotMotionState,
        edge_state: MandelbrotEdgeState,
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

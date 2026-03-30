from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

import pygame
import reactivex
from reactivex import operators as ops
from reactivex.subject import BehaviorSubject

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
        self._edge_state = BehaviorSubject(MandelbrotEdgeState())
        self._wire_edges()

    @cached_property
    def _observable(self) -> reactivex.Observable[MandelbrotControlState]:
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
            reactivex.combine_latest(keyboard_state, gamepad_state, self._edge_state),
            ops.map(lambda latest: self._to_state(*latest)),
            ops.distinct_until_changed(),
        )
        return instrument_input_stream(
            stream,
            tap=self._debug_tap,
            stage=InputDebugStage.LOGICAL,
            stream_name="mandelbrot.controls",
            source_id="mandelbrot",
            upstream_ids=("keyboard", "gamepad"),
        )

    def observable(self) -> reactivex.Observable[MandelbrotControlState]:
        return self._observable

    def _wire_edges(self) -> None:
        self._keyboard.key_pressed(pygame.K_LEFTBRACKET).subscribe(
            on_next=lambda _event: self._bump(previous_view_mode_revision=1)
        )
        self._keyboard.key_pressed(pygame.K_RIGHTBRACKET).subscribe(
            on_next=lambda _event: self._bump(next_view_mode_revision=1)
        )
        self._keyboard.key_pressed(pygame.K_i).subscribe(
            on_next=lambda _event: self._bump(toggle_debug_revision=1)
        )
        self._keyboard.key_pressed(pygame.K_p).subscribe(
            on_next=lambda _event: self._bump(toggle_fps_revision=1)
        )
        self._keyboard.key_pressed(pygame.K_0).subscribe(
            on_next=lambda _event: self._bump(
                toggle_orientation_revision=1,
                orientation_kind="rectangle",
            )
        )
        self._keyboard.key_pressed(pygame.K_9).subscribe(
            on_next=lambda _event: self._bump(
                toggle_orientation_revision=1,
                orientation_kind="cube",
            )
        )
        self._gamepad.button_tapped(GamepadButton.ZR).subscribe(
            on_next=lambda _button: self._bump(next_view_mode_revision=1)
        )
        self._gamepad.button_tapped(GamepadButton.ZL).subscribe(
            on_next=lambda _button: self._bump(previous_view_mode_revision=1)
        )
        self._gamepad.button_tapped(GamepadButton.HOME).subscribe(
            on_next=lambda _button: self._bump(toggle_auto_mode_revision=1)
        )
        self._gamepad.button_tapped(GamepadButton.NORTH).subscribe(
            on_next=lambda _button: self._bump(palette_revision=1, palette_delta=1)
        )
        self._gamepad.button_tapped(GamepadButton.WEST).subscribe(
            on_next=lambda _button: self._bump(palette_revision=1, palette_delta=-1)
        )

    def _bump(self, **updates: int | str | None) -> None:
        state = self._edge_state.value
        next_state = MandelbrotEdgeState(
            next_view_mode_revision=state.next_view_mode_revision + int(
                updates.get("next_view_mode_revision", 0)
            ),
            previous_view_mode_revision=state.previous_view_mode_revision + int(
                updates.get("previous_view_mode_revision", 0)
            ),
            toggle_debug_revision=state.toggle_debug_revision + int(
                updates.get("toggle_debug_revision", 0)
            ),
            toggle_fps_revision=state.toggle_fps_revision + int(
                updates.get("toggle_fps_revision", 0)
            ),
            toggle_orientation_revision=state.toggle_orientation_revision + int(
                updates.get("toggle_orientation_revision", 0)
            ),
            orientation_kind=updates.get("orientation_kind", state.orientation_kind),
            toggle_auto_mode_revision=state.toggle_auto_mode_revision + int(
                updates.get("toggle_auto_mode_revision", 0)
            ),
            palette_revision=state.palette_revision + int(
                updates.get("palette_revision", 0)
            ),
            palette_delta=int(updates.get("palette_delta", state.palette_delta)),
        )
        self._edge_state.on_next(next_state)

    def _to_state(
        self,
        keyboard_state: tuple[object, ...],
        gamepad_state: tuple[object, ...],
        edge_state: MandelbrotEdgeState,
    ) -> MandelbrotControlState:
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

        return MandelbrotControlState(
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

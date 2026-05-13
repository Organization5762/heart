from collections import deque
from dataclasses import replace

import pygame
from manyfold.graph import SubscriptionLike

from heart.device import Cube, Rectangle
from heart.peripheral.core.input import (CyclePaletteCommand,
                                         MandelbrotCommand,
                                         MandelbrotControlProfile,
                                         MandelbrotMotionState,
                                         NextViewModeCommand,
                                         PreviousViewModeCommand,
                                         SetOrientationCommand,
                                         ToggleAutoModeCommand,
                                         ToggleDebugCommand, ToggleFpsCommand,
                                         ToggleOrientationCommand)
from heart.renderers.mandelbrot.controls import SceneControls


class KeyboardControls:
    def __init__(
        self,
        scene_controls: SceneControls,
        profile: MandelbrotControlProfile,
    ) -> None:
        self.scene_controls = scene_controls
        self._latest_motion_state = MandelbrotMotionState()
        self._pending_commands: deque[MandelbrotCommand] = deque()
        self._subscriptions: list[SubscriptionLike] = [
            profile.motion_state.subscribe(on_next=self._set_latest_motion_state),
            profile.command_events.subscribe(on_next=self._queue_command),
        ]

    def dispose(self) -> None:
        for subscription in self._subscriptions:
            subscription.dispose()
        self._subscriptions.clear()

    def update(self) -> None:
        state = self._motion_state_with_keyboard_fallback()

        if state.move_x != 0 or state.move_y != 0:
            self.scene_controls._move(
                state.move_x,
                state.move_y,
                multiplier=state.move_multiplier,
            )

        if state.pan_x != 0 or state.pan_y != 0:
            self.scene_controls._move(
                state.pan_x,
                state.pan_y,
                explicit_mode="panning",
                multiplier=state.move_multiplier,
            )

        if state.zoom_in:
            self.scene_controls._zoom_in()
        if state.zoom_out:
            self.scene_controls._zoom_out()
        if state.increase_iterations:
            self.scene_controls._increase_max_iterations()
        if state.decrease_iterations:
            self.scene_controls._decrease_max_iterations()

        while self._pending_commands:
            self._apply_command(self._pending_commands.popleft())

    def _apply_command(self, command: MandelbrotCommand) -> None:
        match command:
            case NextViewModeCommand():
                self.scene_controls._increment_view_mode()
            case PreviousViewModeCommand():
                self.scene_controls._decrement_view_mode()
            case ToggleDebugCommand():
                self.scene_controls._toggle_debug()
            case ToggleFpsCommand():
                self.scene_controls._toggle_fps()
            case SetOrientationCommand():
                self._apply_orientation(command.orientation_kind)
            case ToggleOrientationCommand():
                self._toggle_orientation()
            case ToggleAutoModeCommand():
                if self.scene_controls.state.mode == "auto":
                    self.scene_controls.state.reset()
                    self.scene_controls.state.set_mode_free()
                else:
                    self.scene_controls.state.reset()
                    self.scene_controls.state.set_mode_auto()
            case CyclePaletteCommand():
                self.scene_controls.cycle_palette(forward=command.palette_delta >= 0)

    def _apply_orientation(self, orientation_kind: str | None) -> None:
        if orientation_kind == "rectangle":
            self.scene_controls.state.orientation = Rectangle(
                self.scene_controls.state.orientation.layout
            )
        elif orientation_kind == "cube":
            self.scene_controls.state.orientation = Cube(
                self.scene_controls.state.orientation.layout
            )

    def _toggle_orientation(self) -> None:
        orientation = self.scene_controls.state.orientation
        match orientation:
            case Cube():
                self.scene_controls.state.orientation = Rectangle(orientation.layout)
            case Rectangle():
                self.scene_controls.state.orientation = Cube(orientation.layout)

    def _queue_command(self, command: MandelbrotCommand) -> None:
        self._pending_commands.append(command)

    def _set_latest_motion_state(self, state: MandelbrotMotionState) -> None:
        self._latest_motion_state = state

    def _motion_state_with_keyboard_fallback(self) -> MandelbrotMotionState:
        keyboard_state = self._sample_keyboard_motion_state()
        if keyboard_state is None:
            return self._latest_motion_state
        if not self._has_keyboard_input(keyboard_state):
            return self._latest_motion_state
        if self._has_motion_input(self._latest_motion_state):
            return self._latest_motion_state
        return replace(
            self._latest_motion_state,
            move_x=keyboard_state.move_x,
            move_y=keyboard_state.move_y,
            zoom_in=keyboard_state.zoom_in,
            zoom_out=keyboard_state.zoom_out,
            increase_iterations=keyboard_state.increase_iterations,
            decrease_iterations=keyboard_state.decrease_iterations,
        )

    def _sample_keyboard_motion_state(self) -> MandelbrotMotionState | None:
        try:
            pygame.event.pump()
            keys = pygame.key.get_pressed()
        except pygame.error:
            return None

        def pressed(key: int) -> bool:
            try:
                return bool(keys[key])
            except (IndexError, KeyError):
                return False

        return MandelbrotMotionState(
            move_x=float(pressed(pygame.K_d)) - float(pressed(pygame.K_a)),
            move_y=float(pressed(pygame.K_s)) - float(pressed(pygame.K_w)),
            zoom_in=pressed(pygame.K_e),
            zoom_out=pressed(pygame.K_q),
            increase_iterations=pressed(pygame.K_j),
            decrease_iterations=pressed(pygame.K_k),
        )

    @staticmethod
    def _has_keyboard_input(state: MandelbrotMotionState) -> bool:
        return (
            state.move_x != 0
            or state.move_y != 0
            or state.zoom_in
            or state.zoom_out
            or state.increase_iterations
            or state.decrease_iterations
        )

    @staticmethod
    def _has_motion_input(state: MandelbrotMotionState) -> bool:
        return (
            state.move_x != 0
            or state.move_y != 0
            or state.pan_x != 0
            or state.pan_y != 0
            or state.zoom_in
            or state.zoom_out
            or state.increase_iterations
            or state.decrease_iterations
        )

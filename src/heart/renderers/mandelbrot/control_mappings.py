from dataclasses import replace

import pygame

from heart.device import Cube, Rectangle
from heart.peripheral.core.input import (CyclePaletteCommand, GamepadButton,
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
        self._profile = profile
        self._last_sampled_buttons: frozenset[GamepadButton] = frozenset()
        self._last_sampled_keys: frozenset[int] = frozenset()

    def dispose(self) -> None:
        return None

    def update(self) -> None:
        keys = self._sample_keyboard_keys()
        state = self._motion_state_from_snapshots(keys)

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

        for command in self._sample_keyboard_commands(keys):
            self._apply_command(command)

        for command in self._sample_gamepad_commands():
            self._apply_command(command)

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

    def _motion_state_from_snapshots(
        self,
        keys: frozenset[int] | None,
    ) -> MandelbrotMotionState:
        sampled_gamepad_state = self._sample_gamepad_motion_state()
        if sampled_gamepad_state is not None and self._has_motion_input(
            sampled_gamepad_state
        ):
            return sampled_gamepad_state

        keyboard_state = self._sample_keyboard_motion_state(keys)
        if keyboard_state is None:
            return MandelbrotMotionState()
        if not self._has_keyboard_input(keyboard_state):
            return sampled_gamepad_state or MandelbrotMotionState()
        return replace(
            sampled_gamepad_state or MandelbrotMotionState(),
            move_x=keyboard_state.move_x,
            move_y=keyboard_state.move_y,
            zoom_in=keyboard_state.zoom_in,
            zoom_out=keyboard_state.zoom_out,
            increase_iterations=keyboard_state.increase_iterations,
            decrease_iterations=keyboard_state.decrease_iterations,
        )

    def _sample_gamepad_motion_state(self) -> MandelbrotMotionState | None:
        try:
            return self._profile.sample_gamepad_motion_state()
        except (AttributeError, pygame.error):
            return None

    def _sample_gamepad_commands(self) -> tuple[MandelbrotCommand, ...]:
        try:
            buttons = self._profile.sample_gamepad_buttons()
        except (AttributeError, pygame.error):
            return ()
        pressed = buttons - self._last_sampled_buttons
        self._last_sampled_buttons = buttons
        commands: list[MandelbrotCommand] = []
        if GamepadButton.ZR in pressed:
            commands.append(NextViewModeCommand(source="gamepad.zr.sampled"))
        if GamepadButton.ZL in pressed:
            commands.append(PreviousViewModeCommand(source="gamepad.zl.sampled"))
        if GamepadButton.NORTH in pressed:
            commands.append(
                CyclePaletteCommand(source="gamepad.north.sampled", palette_delta=1)
            )
        if GamepadButton.WEST in pressed:
            commands.append(
                CyclePaletteCommand(source="gamepad.west.sampled", palette_delta=-1)
            )
        return tuple(commands)

    def _sample_keyboard_keys(self) -> frozenset[int] | None:
        try:
            pygame.event.pump()
            keys = pygame.key.get_pressed()
        except pygame.error:
            return None

        pressed_keys: set[int] = set()
        for key in (
            pygame.K_a,
            pygame.K_d,
            pygame.K_e,
            pygame.K_i,
            pygame.K_j,
            pygame.K_k,
            pygame.K_LEFTBRACKET,
            pygame.K_p,
            pygame.K_q,
            pygame.K_RIGHTBRACKET,
            pygame.K_s,
            pygame.K_w,
            pygame.K_0,
            pygame.K_9,
        ):
            if self._key_pressed(keys, key):
                pressed_keys.add(key)
        return frozenset(pressed_keys)

    def _sample_keyboard_motion_state(
        self,
        keys: frozenset[int] | None,
    ) -> MandelbrotMotionState | None:
        if keys is None:
            return None

        def pressed(key: int) -> bool:
            return key in keys

        return MandelbrotMotionState(
            move_x=float(pressed(pygame.K_d)) - float(pressed(pygame.K_a)),
            move_y=float(pressed(pygame.K_s)) - float(pressed(pygame.K_w)),
            zoom_in=pressed(pygame.K_e),
            zoom_out=pressed(pygame.K_q),
            increase_iterations=pressed(pygame.K_j),
            decrease_iterations=pressed(pygame.K_k),
        )

    def _sample_keyboard_commands(
        self,
        keys: frozenset[int] | None,
    ) -> tuple[MandelbrotCommand, ...]:
        if keys is None:
            self._last_sampled_keys = frozenset()
            return ()

        tapped = keys - self._last_sampled_keys
        self._last_sampled_keys = keys
        commands: list[MandelbrotCommand] = []
        if pygame.K_RIGHTBRACKET in tapped:
            commands.append(NextViewModeCommand(source="keyboard.right_bracket"))
        if pygame.K_LEFTBRACKET in tapped:
            commands.append(PreviousViewModeCommand(source="keyboard.left_bracket"))
        if pygame.K_i in tapped:
            commands.append(ToggleDebugCommand(source="keyboard.i"))
        if pygame.K_p in tapped:
            commands.append(ToggleFpsCommand(source="keyboard.p"))
        if pygame.K_0 in tapped:
            commands.append(
                SetOrientationCommand(source="keyboard.0", orientation_kind="rectangle")
            )
        if pygame.K_9 in tapped:
            commands.append(
                SetOrientationCommand(source="keyboard.9", orientation_kind="cube")
            )
        return tuple(commands)

    @staticmethod
    def _key_pressed(keys: pygame.key.ScancodeWrapper, key: int) -> bool:
        try:
            return bool(keys[key])
        except (IndexError, KeyError):
            return False

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

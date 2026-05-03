from collections import deque

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
        profile.motion_state.subscribe(on_next=self._set_latest_motion_state)
        profile.command_events.subscribe(on_next=self._queue_command)

    def update(self) -> None:
        state = self._latest_motion_state

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

from heart.device import Cube, Rectangle
from heart.peripheral.core.input import (MandelbrotControlProfile,
                                         MandelbrotControlState)
from heart.renderers.mandelbrot.controls import SceneControls

DEFAULT_STICK_MULTIPLIER = 1.0


class KeyboardControls:
    def __init__(
        self,
        scene_controls: SceneControls,
        profile: MandelbrotControlProfile,
    ) -> None:
        self.scene_controls = scene_controls
        self._latest_state = MandelbrotControlState()
        self._previous_state = MandelbrotControlState()
        profile.observable().subscribe(on_next=self._set_latest_state)

    def update(self) -> None:
        state = self._latest_state

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

        if state.next_view_mode_revision != self._previous_state.next_view_mode_revision:
            self.scene_controls._increment_view_mode()
        if (
            state.previous_view_mode_revision
            != self._previous_state.previous_view_mode_revision
        ):
            self.scene_controls._decrement_view_mode()
        if state.toggle_debug_revision != self._previous_state.toggle_debug_revision:
            self.scene_controls._toggle_debug()
        if (
            state.toggle_fps_revision != self._previous_state.toggle_fps_revision
            or self._minus_combo_rising(state)
        ):
            self.scene_controls._toggle_fps()

        if state.toggle_orientation_revision != self._previous_state.toggle_orientation_revision:
            self._apply_keyboard_orientation(state.orientation_kind)
        elif self._plus_combo_rising(state):
            orientation = self.scene_controls.state.orientation
            match orientation:
                case Cube():
                    self.scene_controls.state.orientation = Rectangle(
                        orientation.layout
                    )
                case Rectangle():
                    self.scene_controls.state.orientation = Cube(orientation.layout)

        if (
            state.toggle_auto_mode_revision
            != self._previous_state.toggle_auto_mode_revision
        ):
            if self.scene_controls.state.mode == "auto":
                self.scene_controls.state.reset()
                self.scene_controls.state.set_mode_free()
            else:
                self.scene_controls.state.reset()
                self.scene_controls.state.set_mode_auto()

        if state.palette_revision != self._previous_state.palette_revision:
            self.scene_controls.cycle_palette(forward=state.palette_delta >= 0)

        self._previous_state = state

    def _apply_keyboard_orientation(self, orientation_kind: str | None) -> None:
        if orientation_kind == "rectangle":
            self.scene_controls.state.orientation = Rectangle(
                self.scene_controls.state.orientation.layout
            )
        elif orientation_kind == "cube":
            self.scene_controls.state.orientation = Cube(
                self.scene_controls.state.orientation.layout
            )

    def _plus_combo_rising(self, state: MandelbrotControlState) -> bool:
        current = state.home_modifier and state.plus_held
        previous = self._previous_state.home_modifier and self._previous_state.plus_held
        return current and not previous

    def _minus_combo_rising(self, state: MandelbrotControlState) -> bool:
        current = state.home_modifier and state.minus_held
        previous = (
            self._previous_state.home_modifier and self._previous_state.minus_held
        )
        return current and not previous

    def _set_latest_state(self, state: MandelbrotControlState) -> None:
        self._latest_state = state

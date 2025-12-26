from abc import ABC, abstractmethod
from collections import defaultdict

import pygame

from heart.device import Cube, Rectangle
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.gamepad.peripheral_mappings import (BitDoLite2,
                                                          BitDoLite2Bluetooth,
                                                          DpadType,
                                                          SwitchLikeMapping,
                                                          SwitchProMapping)
from heart.renderers.mandelbrot.controls import SceneControls
from heart.utilities.env import Configuration

DEFAULT_STICK_MULTIPLIER = 1.0


class SceneControlsMapping(ABC):
    def update(self):
        self.update_movement()
        self.update_zoom()
        self.update_iterations()
        self.update_mode()
        self.update_additional()

    @abstractmethod
    def update_movement(self):
        """Update pan/cursor movement."""
        pass

    @abstractmethod
    def update_zoom(self):
        """Update zoom."""
        pass

    @abstractmethod
    def update_iterations(self):
        """Update max_iterations used for evaluating if element in set."""
        pass

    @abstractmethod
    def update_mode(self):
        """Cycle through the view modes.

        0 - full mandelbrot
        1 - split view (with mandelbrot selected)
        2 - split view (with julia selected)
        3 - full julia

        """
        pass

    def update_additional(self):
        """Catch all mostly for debug controls."""
        pass


class KeyboardControls(SceneControlsMapping):
    def __init__(self, scene_controls: SceneControls):
        self.scene_controls = scene_controls
        self.key_pressed_last_frame = defaultdict(lambda: False)

    def update_movement(self):
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_w]:
            self.scene_controls._move_up()
        if pressed[pygame.K_s]:
            self.scene_controls._move_down()
        if pressed[pygame.K_a]:
            self.scene_controls._move_left()
        if pressed[pygame.K_d]:
            self.scene_controls._move_right()

    def update_zoom(self):
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_q]:
            self.scene_controls._zoom_out()
        if pressed[pygame.K_e]:
            self.scene_controls._zoom_in()

    def update_iterations(self):
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_j]:
            self.scene_controls._increase_max_iterations()
        if pressed[pygame.K_k]:
            self.scene_controls._decrease_max_iterations()

    def update_mode(self):
        pressed = pygame.key.get_pressed()
        if (
            pressed[pygame.K_LEFTBRACKET]
            and not self.key_pressed_last_frame[pygame.K_LEFTBRACKET]
        ):
            self.scene_controls._decrement_view_mode()
        self.key_pressed_last_frame[pygame.K_LEFTBRACKET] = pressed[
            pygame.K_LEFTBRACKET
        ]

        if (
            pressed[pygame.K_RIGHTBRACKET]
            and not self.key_pressed_last_frame[pygame.K_RIGHTBRACKET]
        ):
            self.scene_controls._increment_view_mode()
        self.key_pressed_last_frame[pygame.K_RIGHTBRACKET] = pressed[
            pygame.K_RIGHTBRACKET
        ]

    def update_additional(self):
        pressed = pygame.key.get_pressed()
        if pressed[pygame.K_i] and not self.key_pressed_last_frame[pygame.K_i]:
            self.scene_controls._toggle_debug()
        self.key_pressed_last_frame[pygame.K_i] = pressed[pygame.K_i]

        if pressed[pygame.K_p] and not self.key_pressed_last_frame[pygame.K_p]:
            self.scene_controls._toggle_fps()
        self.key_pressed_last_frame[pygame.K_p] = pressed[pygame.K_p]

        if pressed[pygame.K_0] and not self.key_pressed_last_frame[pygame.K_0]:
            self.scene_controls.state.orientation = Rectangle(
                self.scene_controls.state.orientation.layout
            )
        self.key_pressed_last_frame[pygame.K_0] = pressed[pygame.K_0]

        if pressed[pygame.K_9] and not self.key_pressed_last_frame[pygame.K_9]:
            self.scene_controls.state.orientation = Cube(
                self.scene_controls.state.orientation.layout
            )
        self.key_pressed_last_frame[pygame.K_9] = pressed[pygame.K_9]


class SwitchLikeControls(SceneControlsMapping, ABC):
    @property
    @abstractmethod
    def mapping(self) -> SwitchLikeMapping:
        pass

    @property
    @abstractmethod
    def dead_zone(self) -> float:
        pass

    def __init__(self, scene_controls: SceneControls, gamepad: Gamepad):
        self.scene_controls = scene_controls
        self.gamepad = gamepad

    def update(self):
        self.gamepad.update()
        super().update()

    def update_movement(self):
        if self.gamepad.is_held(self.mapping.BUTTON_B):
            multiplier = 2.0
        else:
            multiplier = 1.0
        self._handle_stick(multiplier)
        self._handle_dpad()

    def update_zoom(self):
        if self.gamepad.axis_passed_threshold(self.mapping.AXIS_R):
            self.scene_controls._zoom_in()
        if self.gamepad.axis_passed_threshold(self.mapping.AXIS_L):
            self.scene_controls._zoom_out()

    def update_iterations(self):
        if self.gamepad.is_held(self.mapping.BUTTON_HOME):
            # i.e. modifier button held
            return
        if self.gamepad.is_held(self.mapping.BUTTON_PLUS):
            self.scene_controls._increase_max_iterations()
        if self.gamepad.is_held(self.mapping.BUTTON_MINUS):
            self.scene_controls._decrease_max_iterations()

    def update_mode(self):
        if self.gamepad.was_tapped(self.mapping.BUTTON_ZR):
            self.scene_controls._increment_view_mode()
        if self.gamepad.was_tapped(self.mapping.BUTTON_ZL):
            self.scene_controls._decrement_view_mode()
        # if self.controller.get_button_toggle(self.mapping.BUTTON_R):
        #     self.scene_controls._increment_view_mode()
        # if self.controller.get_button_toggle(self.mapping.BUTTON_L):
        #     self.scene_controls._decrement_view_mode()

    def update_additional(self):
        if self.gamepad.is_held(self.mapping.BUTTON_HOME):
            if self.gamepad.was_tapped(self.mapping.BUTTON_MINUS):
                self.scene_controls._toggle_fps()

            if self.gamepad.is_held(
                self.mapping.BUTTON_HOME
            ) and self.gamepad.was_tapped(self.mapping.BUTTON_PLUS):
                orientation = self.scene_controls.state.orientation
                match orientation:
                    case Cube():
                        self.scene_controls.state.orientation = Rectangle(
                            orientation.layout
                        )
                    case Rectangle():
                        self.scene_controls.state.orientation = Cube(orientation.layout)
            return

        if self.gamepad.was_tapped(self.mapping.BUTTON_HOME):
            if self.scene_controls.state.mode == "auto":
                self.scene_controls.state.reset()
                self.scene_controls.state.set_mode_free()
            else:
                self.scene_controls.state.reset()
                self.scene_controls.state.set_mode_auto()

        if self.gamepad.was_tapped(self.mapping.BUTTON_Y):
            self.scene_controls.cycle_palette(forward=True)
        if self.gamepad.was_tapped(self.mapping.BUTTON_X):
            self.scene_controls.cycle_palette(forward=False)

    def _handle_stick(self, multiplier: float = DEFAULT_STICK_MULTIPLIER):
        x_mov = self.gamepad.axis_value(self.mapping.AXIS_LEFT_X, self.dead_zone)
        y_mov = self.gamepad.axis_value(self.mapping.AXIS_LEFT_Y, self.dead_zone)

        rx_mov = self.gamepad.axis_value(self.mapping.AXIS_RIGHT_X, self.dead_zone)
        ry_mov = self.gamepad.axis_value(self.mapping.AXIS_RIGHT_Y, self.dead_zone)

        if x_mov != 0 or y_mov != 0:
            self.scene_controls._move(x_mov, y_mov, multiplier=multiplier)

        if rx_mov != 0 or ry_mov != 0:
            self.scene_controls._move(
                rx_mov, ry_mov, explicit_mode="panning", multiplier=multiplier
            )

    def _handle_dpad(self):
        if self.mapping.get_dpad_type() == DpadType.HAT:
            x_dir, y_dir = self.gamepad.joystick.get_hat(self.mapping.DPAD_HAT)
            if x_dir != 0 or y_dir != 0:
                self.scene_controls._move(
                    x_dir, -y_dir
                )  # opposite polarity for y-dir wrt _move(...)

        elif self.mapping.get_dpad_type() == DpadType.BUTTONS:
            if self.gamepad.is_held(self.mapping.DPAD_UP):
                self.scene_controls._move_up()
            if self.gamepad.is_held(self.mapping.DPAD_DOWN):
                self.scene_controls._move_down()
            if self.gamepad.is_held(self.mapping.DPAD_LEFT):
                self.scene_controls._move_left()
            if self.gamepad.is_held(self.mapping.DPAD_RIGHT):
                self.scene_controls._move_right()


class BitDoLite2Controls(SwitchLikeControls):
    mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()
    dead_zone = 0.1


class SwitchProControls(SwitchLikeControls):
    mapping = SwitchProMapping()
    dead_zone = 0.35  # rip

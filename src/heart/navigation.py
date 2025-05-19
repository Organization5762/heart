import time
from collections import defaultdict

import pygame
from pygame.time import Clock

from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.display.renderers.color import RenderColor
from heart.display.renderers.slide import SlideTransitionRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.firmware_io.constants import BUTTON_LONG_PRESS, BUTTON_PRESS, SWITCH_ROTATION
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad.peripheral_mappings import BitDoLite2Bluetooth, BitDoLite2
from heart.utilities.env import Configuration


class AppController(BaseRenderer):
    def __init__(self) -> None:
        self.modes = GameModes()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        self.modes.initialize(window, clock, peripheral_manager, orientation)
        super().initialize(window, clock, peripheral_manager, orientation)

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list[BaseRenderer]:
        return self.modes.get_renderers(peripheral_manager=peripheral_manager)

    def add_sleep_mode(self) -> None:
        sleep_title = [
            SpritesheetLoop(
                sheet_file_path=f"kirby_sleep_64.png",
                metadata_file_path=f"kirby_sleep_64.json",
                image_scale=0.5,
                offset_y=-5,
                disable_input=True,
            ),
            TextRendering(
                text=["sleep"],
                font="Roboto",
                font_size=14,
                color=Color.kirby(),
                y_location=35,
            ),
        ]
        mode = self.add_mode(sleep_title)
        mode.add_renderer(RenderColor(Color(0, 0, 0)))

    def add_scene(self) -> "MultiScene":
        new_scene = MultiScene(scenes=[])
        self.modes.add_new_pages(new_scene)
        return new_scene

    def add_mode(
        self, title: str | list[BaseRenderer] | BaseRenderer | None = None
    ) -> "ComposedRenderer":
        # TODO: Add a navigation page back in
        result = ComposedRenderer([])
        if title is None:
            title = "Untitled"

        if isinstance(title, str):
            title_renderer = TextRendering(
                text=[title],
                font="Roboto",
                font_size=14,
                color=Color(255, 105, 180),
            )
        elif isinstance(title, BaseRenderer):
            title_renderer = title
        elif isinstance(title, list):
            title_renderer = ComposedRenderer(title)
        else:
            raise ValueError("Title must be a string or BaseRenderer, got: ", title)

        # TODO: Clean-up
        self.modes.title_renderers.append(title_renderer)
        self.modes.add_new_pages(result)
        return result

    def is_empty(self) -> bool:
        return len(self.modes.renderers) == 0


class GameModes(BaseRenderer):
    """GameModes represents a collection of modes in the game loop where different
    renderers can be added.

    Navigation is built-in to this, assuming the user long-presses

    """

    def __init__(self) -> None:
        self.title_renderers: list[BaseRenderer] = []
        self.renderers: list[BaseRenderer] = []
        self.in_select_mode = True
        self.last_long_button_value = 0
        self.mode_offset = 0
        self._active_mode_index = 0
        self.time_last_debugging_press = None

        self.previous_mode_index = 0
        self.sliding_transition = None
        self.key_pressed_last_frame = defaultdict(lambda: False)
        self.gamepad_last_frame = defaultdict(lambda: False)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        for renderer in self.renderers:
            renderer.initialize(window, clock, peripheral_manager, orientation)

    def add_new_pages(self, *renderers: "BaseRenderer") -> None:
        self.renderers.extend(renderers)

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list[BaseRenderer]:
        self.handle_inputs(peripheral_manager)
        active_renderer = self.active_renderer(mode_offset=self.mode_offset)
        renderers = active_renderer.get_renderers(peripheral_manager)
        return renderers

    def _process_gamepad_key_input(self, peripheral_manager: PeripheralManager):
        gamepad = peripheral_manager.get_gamepad()
        mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()

        switch = peripheral_manager._deprecated_get_main_switch()
        gamepad.update()

        payload = None
        if gamepad.is_connected() and self.in_select_mode:
            # print("gamepad connectee")
            x_dir, y_dir = gamepad.get_dpad_value()
            if x_dir != 0 and x_dir != self.gamepad_last_frame[f"DPAD_X"]:
                payload = {
                    "event_type": SWITCH_ROTATION,
                    "data": switch.rotational_value + x_dir,
                }
            self.gamepad_last_frame[f"DPAD_X"] = x_dir
            if y_dir != 0 and y_dir != self.gamepad_last_frame[f"DPAD_Y"]:
                payload = {"event_type": BUTTON_LONG_PRESS, "data": 1}
            self.gamepad_last_frame[f"DPAD_Y"] = y_dir

        # i.e. this branch to listen for exit request when inside a scene
        elif gamepad.is_connected():
            # i.e. press plus + minus to exit from any mode
            plus_tapped = gamepad.is_held(mapping.BUTTON_PLUS)
            minus_tapped = gamepad.is_held(mapping.BUTTON_MINUS)
            if plus_tapped and minus_tapped:
                payload = {"event_type": BUTTON_LONG_PRESS, "data": 1}

        if payload is not None:
            switch.update_due_to_data(payload)

        pygame.display.set_caption(
            f"R: {switch.get_rotational_value()}, NR: {switch.get_rotation_since_last_button_press()}, B: {switch.get_button_value()}, BL: {switch.get_long_button_value()}"
        )


    def _process_debugging_key_presses(
        self, peripheral_manager: PeripheralManager
    ) -> None:
        # Only run this if not on the Pi
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            return

        keys = pygame.key.get_pressed()

        switch = peripheral_manager._deprecated_get_main_switch()
        payload = None

        # TODO: Start coming up with a better way of handling this + simulating N peripherals all with different signals
        if keys[pygame.K_LEFT] and not self.key_pressed_last_frame[pygame.K_LEFT]:
            payload = {
                "event_type": SWITCH_ROTATION,
                "data": switch.rotational_value - 1,
            }
        self.key_pressed_last_frame[pygame.K_LEFT] = keys[pygame.K_LEFT]

        if keys[pygame.K_RIGHT] and not self.key_pressed_last_frame[pygame.K_RIGHT]:
            payload = {
                "event_type": SWITCH_ROTATION,
                "data": switch.rotational_value + 1,
            }
        self.key_pressed_last_frame[pygame.K_RIGHT] = keys[pygame.K_RIGHT]

        if keys[pygame.K_UP] and not self.key_pressed_last_frame[pygame.K_UP]:
            payload = {"event_type": BUTTON_LONG_PRESS, "data": 1}

        self.key_pressed_last_frame[pygame.K_UP] = keys[pygame.K_UP]

        if keys[pygame.K_DOWN] and not self.key_pressed_last_frame[pygame.K_DOWN]:
            payload = {"event_type": BUTTON_PRESS, "data": 1}

        self.key_pressed_last_frame[pygame.K_DOWN] = keys[pygame.K_DOWN]

        if payload is not None:
            switch.update_due_to_data(payload)

        pygame.display.set_caption(
            f"R: {switch.get_rotational_value()}, NR: {switch.get_rotation_since_last_button_press()}, B: {switch.get_button_value()}, BL: {switch.get_long_button_value()}"
        )

    def handle_inputs(self, peripheral_manager: PeripheralManager) -> None:
        self._process_debugging_key_presses(peripheral_manager)
        self._process_gamepad_key_input(peripheral_manager)
        new_long_button_value = (
            peripheral_manager._deprecated_get_main_switch().get_long_button_value()
        )
        if new_long_button_value != self.last_long_button_value:
            # Swap select modes
            if self.in_select_mode:
                # Combine the offset we're switching out of select mode
                self._active_mode_index += self.mode_offset
                self.mode_offset = 0

            self.in_select_mode = not self.in_select_mode
            self.last_long_button_value = new_long_button_value

        if self.in_select_mode:
            self.mode_offset = (
                peripheral_manager._deprecated_get_main_switch().get_rotation_since_last_long_button_press()
            )

    def active_renderer(self, mode_offset: int) -> BaseRenderer:
        mode_index = (self._active_mode_index + mode_offset) % len(self.renderers)
        last_render_index = len(self.renderers) - 1

        if self.previous_mode_index != mode_index:
            if mode_index == 0 and self.previous_mode_index == last_render_index:
                slide_dir = 1
            elif mode_index == last_render_index and self.previous_mode_index == 0:
                slide_dir = -1
            else:
                slide_dir = (mode_index - self.previous_mode_index)

            self.sliding_transition = SlideTransitionRenderer(
                renderer_A=self.title_renderers[self.previous_mode_index],
                renderer_B=self.title_renderers[mode_index],
                direction=slide_dir,
            )
            self.previous_mode_index = mode_index
            return self.sliding_transition

        if self.sliding_transition is not None:
            if self.sliding_transition.is_done():
                self.sliding_transition = None
            else:
                return self.sliding_transition

        if self.in_select_mode:
            for renderer in self.renderers:
                renderer.reset()
            return self.title_renderers[mode_index]

        self.previous_mode_index = mode_index
        return self.renderers[mode_index]


class ComposedRenderer(BaseRenderer):
    def __init__(self, renderers: list[BaseRenderer]) -> None:
        super().__init__()
        self.renderers: list[BaseRenderer] = renderers

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list[BaseRenderer]:
        result = []
        for renderer in self.renderers:
            result.extend(renderer.get_renderers(peripheral_manager))
        return result

    def add_renderer(self, *renderer: BaseRenderer):
        self.renderers.extend(renderer)

    def reset(self):
        for renderer in self.renderers:
            renderer.reset()

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # TODO: This overlaps a bit with what the environment does
        for renderer in self.renderers:
            renderer._internal_process(window, clock, peripheral_manager, orientation)


class MultiScene(BaseRenderer):
    def __init__(self, scenes: list[BaseRenderer]) -> None:
        super().__init__()
        self.scenes = scenes
        self.current_scene_index = 0
        self.last_switch_value = None
        self.key_pressed_last_frame = defaultdict(lambda: False)
        self.gamepad_last_frame = defaultdict(lambda: False)

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list[BaseRenderer]:
        self._process_input(peripheral_manager)
        # This multi-scene could be composed of multiple renderers
        return [
            *self.scenes[self.current_scene_index].get_renderers(
                peripheral_manager=peripheral_manager
            )
        ]

    def reset(self):
        self.current_scene_index = 0
        for scene in self.scenes:
            scene.reset()

    def _process_input(self, peripheral_manager: PeripheralManager) -> None:
        self._process_switch(peripheral_manager)
        self._process_keyboard()
        self._process_gamepad(peripheral_manager)

    def _process_gamepad(self, peripheral_manager: PeripheralManager):
        gamepad = peripheral_manager.get_gamepad()
        mapping = BitDoLite2Bluetooth() if Configuration.is_pi() else BitDoLite2()

        if gamepad.is_connected():
            x_dir, y_dir = gamepad.joystick.get_hat(mapping.DPAD_HAT)
            if x_dir != 0 and x_dir != self.gamepad_last_frame[f"DPAD_X"]:
                self._increment_scene() if x_dir > 0 else self._decrement_scene()
            self.gamepad_last_frame[f"DPAD_X"] = x_dir

        gamepad.update()

    def _process_switch(self, peripheral_manager: PeripheralManager) -> None:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_button_value()
        )
        if self.last_switch_value and self.last_switch_value != current_value:
            self._increment_scene()

        self.last_switch_value = current_value

    def _process_keyboard(self) -> None:
        if (
            pygame.key.get_pressed()[pygame.K_a]
            and not self.key_pressed_last_frame[pygame.K_a]
        ):
            self._decrement_scene()
        self.key_pressed_last_frame[pygame.K_a] = pygame.key.get_pressed()[pygame.K_a]

        if (
            pygame.key.get_pressed()[pygame.K_d]
            and not self.key_pressed_last_frame[pygame.K_d]
        ):
            self._increment_scene()
        self.key_pressed_last_frame[pygame.K_d] = pygame.key.get_pressed()[pygame.K_d]

    def _set_scene_index(self, index: int) -> None:
        self.current_scene_index = index % len(self.scenes)

    def _increment_scene(self) -> None:
        self.current_scene_index = (self.current_scene_index + 1) % len(self.scenes)

    def _decrement_scene(self) -> None:
        self.current_scene_index = (self.current_scene_index - 1) % len(self.scenes)

from collections import defaultdict

import pygame

from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


class MultiScene(BaseRenderer):
    def __init__(self, scenes: list[BaseRenderer]) -> None:
        super().__init__()
        self.scenes = scenes
        self.current_scene_index = 0
        self.key_pressed_last_frame = defaultdict(lambda: False)

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

    def _process_input(self, peripheral_manager: PeripheralManager) -> None:
        self._process_switch(peripheral_manager)
        self._process_keyboard()

    def _process_switch(self, peripheral_manager: PeripheralManager) -> None:
        current_value = (
            peripheral_manager._deprecated_get_main_switch().get_button_value()
        )
        self._set_scene_index(current_value)

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

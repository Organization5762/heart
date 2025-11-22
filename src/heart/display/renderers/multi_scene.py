from dataclasses import dataclass

import pygame

from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class _MultiSceneState:
    current_scene_index: int = 0
    last_a_pressed: bool = False
    last_d_pressed: bool = False


class MultiScene(AtomicBaseRenderer[_MultiSceneState]):
    def __init__(self, scenes: list[BaseRenderer]) -> None:
        self.scenes = scenes
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ):
        for scene in self.scenes:
            scene.initialize(window, clock, peripheral_manager, orientation)

        # TODO: CRITICAL - On _process_input changed, do this
        self._process_input(peripheral_manager)

        return _MultiSceneState()

    def get_renderers(
        self
    ) -> list[BaseRenderer]:
        current_scene = self.scenes[self.state.current_scene_index]
        return [
            *current_scene.get_renderers()
        ]

    def _process_input(self, peripheral_manager: PeripheralManager) -> None:
        self._process_switch()
        self._process_keyboard()

    def _process_switch(self) -> None:
        current_value = self.get_switch_state().button_value
        self._set_scene_index(current_value)

    def _process_keyboard(self) -> None:
        pressed = pygame.key.get_pressed()
        a_pressed = pressed[pygame.K_a]
        d_pressed = pressed[pygame.K_d]

        state = self.state

        if a_pressed and not state.last_a_pressed:
            self._decrement_scene()

        if d_pressed and not state.last_d_pressed:
            self._increment_scene()

        self.update_state(last_a_pressed=a_pressed, last_d_pressed=d_pressed)

    def _set_scene_index(self, index: int) -> None:
        self.update_state(current_scene_index=index % len(self.scenes))

    def _increment_scene(self) -> None:
        self.update_state(
            current_scene_index=(self.state.current_scene_index + 1)
            % len(self.scenes)
        )

    def _decrement_scene(self) -> None:
        self.update_state(
            current_scene_index=(self.state.current_scene_index - 1)
            % len(self.scenes)
        )

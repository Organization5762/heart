from dataclasses import dataclass

import pygame

from heart.device import Orientation
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.display.renderers.internal import SwitchStateConsumer
from heart.peripheral.core.manager import PeripheralManager


@dataclass(frozen=True)
class _MultiSceneState:
    current_scene_index: int = 0
    last_a_pressed: bool = False
    last_d_pressed: bool = False


class MultiScene(SwitchStateConsumer, AtomicBaseRenderer[_MultiSceneState]):
    def __init__(self, scenes: list[BaseRenderer]) -> None:
        self.scenes = scenes

        SwitchStateConsumer.__init__(self)
        AtomicBaseRenderer.__init__(self)

    def _create_initial_state(self) -> _MultiSceneState:
        return _MultiSceneState()

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list[BaseRenderer]:
        self._process_input(peripheral_manager)
        # This multi-scene could be composed of multiple renderers
        current_scene = self.scenes[self.state.current_scene_index]
        return [
            *current_scene.get_renderers(peripheral_manager=peripheral_manager)
        ]

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: "Orientation",
    ) -> None:
        self.bind_switch(peripheral_manager)
        for scene in self.scenes:
            scene.initialize(window, clock, peripheral_manager, orientation)
        super().initialize(window, clock, peripheral_manager, orientation)

    def _process_input(self, peripheral_manager: PeripheralManager) -> None:
        self._process_switch(peripheral_manager)
        self._process_keyboard()

    def _process_switch(self, peripheral_manager: PeripheralManager) -> None:
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

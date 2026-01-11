from __future__ import annotations

from dataclasses import dataclass

import pygame

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)


@dataclass
class MultiSceneState:
    current_button_value: int = 0
    offset_of_button_value: int | None = None


class MultiScene(StatefulBaseRenderer[MultiSceneState]):
    def __init__(
        self,
        scenes: list[RendererSpec],
        renderer_resolver: RendererResolver | None = None,
    ) -> None:
        super().__init__()
        self.scenes = [
            resolve_renderer_spec(scene)
            for scene in scenes
        ]

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        index = self._active_scene_index()
        return [*self.scenes[index].get_renderers()]

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> MultiSceneState:
        state = MultiSceneState(current_button_value=0, offset_of_button_value=None)
        self.set_state(state)
        observable = peripheral_manager.get_main_switch_subscription()
        observable.subscribe(on_next=self._process_switch)

        for scene in self.scenes:
            scene.initialize(window, peripheral_manager, orientation)

        return state

    def real_process(
        self, window: DisplayContext, orientation: Orientation
    ) -> None:
        for render in self.get_renderers():
            render.real_process(window=window, orientation=orientation)

    def reset(self) -> None:
        self.state.offset_of_button_value = self.state.current_button_value
        return super().reset()

    def _process_switch(self, switch_value: SwitchState) -> None:
        self.state.current_button_value = switch_value.button_value

    def _active_scene_index(self) -> int:
        offset = self.state.offset_of_button_value or 0
        return (self.state.current_button_value - offset) % len(self.scenes)

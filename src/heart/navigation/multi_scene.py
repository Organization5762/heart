from __future__ import annotations

from dataclasses import dataclass

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

from .native_scene_manager import (SceneManagerBackend,
                                   build_scene_manager_backend)
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
        scene_manager_backend: SceneManagerBackend | None = None,
    ) -> None:
        super().__init__()
        self.scenes = [
            resolve_renderer_spec(scene, renderer_resolver)
            for scene in scenes
        ]
        self._navigation_subscription = None
        scene_names = [scene.name for scene in self.scenes]
        self._scene_manager = scene_manager_backend or build_scene_manager_backend(
            scene_names
        )

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
        self._navigation_subscription = (
            peripheral_manager.navigation_profile.subscribe_events(
                on_activate=self._process_activate,
            )
        )

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
        self._scene_manager.reset_button_offset(self.state.current_button_value)
        return super().reset()

    def _process_activate(self, _event: object) -> None:
        self.state.current_button_value += 1

    def _active_scene_index(self) -> int:
        return self._scene_manager.active_scene_index(self.state.current_button_value)

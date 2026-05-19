from __future__ import annotations

from dataclasses import dataclass

from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

from .composed_renderer import ComposedRenderer
from .native_scene_manager import (SceneManagerBackend,
                                   build_scene_manager_backend)
from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)


@dataclass
class MultiSceneState:
    current_button_value: int = 0
    offset_of_button_value: int | None = None
    peripheral_manager: PeripheralManager | None = None


class MultiScene(StatefulBaseRenderer[MultiSceneState]):
    def __init__(
        self,
        scenes: list[RendererSpec],
        renderer_resolver: RendererResolver | None = None,
        scene_manager_backend: SceneManagerBackend | None = None,
    ) -> None:
        super().__init__()
        self.scenes = [
            resolve_renderer_spec(scene, renderer_resolver) for scene in scenes
        ]
        self._navigation_subscription = None
        self._last_active_scene_index: int | None = None
        scene_names = [scene.name for scene in self.scenes]
        self._scene_manager = scene_manager_backend or build_scene_manager_backend(
            scene_names
        )

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        index = self._active_scene_index()
        self._reset_previous_active_scene(index)
        active_scene = self.scenes[index]
        self.device_display_mode = active_scene.device_display_mode
        return [*active_scene.get_renderers()]

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> MultiSceneState:
        state = MultiSceneState(
            current_button_value=0,
            offset_of_button_value=None,
            peripheral_manager=peripheral_manager,
        )
        self.set_state(state)
        self._navigation_subscription = peripheral_manager.input_io.navigation.subscribe_events(
            on_activate=self._process_activate,
        )

        if self.scenes:
            active_scene_index = self._active_scene_index()
            self._last_active_scene_index = active_scene_index
            self.device_display_mode = self.scenes[active_scene_index].device_display_mode

        return state

    def real_process(self, window: DisplayContext, orientation: Orientation) -> None:
        if self.scenes:
            self.device_display_mode = self.scenes[
                self._active_scene_index()
            ].device_display_mode

        result = ComposedRenderer.render_batch(
            self.get_renderers(),
            window=window,
            peripheral_manager=self._peripheral_manager(),
            orientation=orientation,
        )
        if result is not None and window.screen is not None:
            window.screen.blit(result, (0, 0))

    def reset(self) -> None:
        if self._state is not None:
            self.state.offset_of_button_value = self.state.current_button_value
            self._scene_manager.reset_button_offset(self.state.current_button_value)
        if self._navigation_subscription is not None:
            self._navigation_subscription.dispose()
            self._navigation_subscription = None
        for scene in self.scenes:
            scene.reset()
        self._last_active_scene_index = None
        self.initialized = False
        super().reset()

    def _process_activate(self, _event: object) -> None:
        previous_index = self._active_scene_index()
        self.state.current_button_value += 1
        next_index = self._active_scene_index()
        if previous_index != next_index:
            self.scenes[previous_index].reset()
            self._last_active_scene_index = next_index

    def _active_scene_index(self) -> int:
        return self._scene_manager.active_scene_index(self.state.current_button_value)

    def _reset_previous_active_scene(self, next_index: int) -> None:
        previous_index = self._last_active_scene_index
        if previous_index is not None and previous_index != next_index:
            self.scenes[previous_index].reset()
        self._last_active_scene_index = next_index

    def _peripheral_manager(self) -> PeripheralManager:
        peripheral_manager = self.state.peripheral_manager
        if peripheral_manager is None:
            raise RuntimeError("MultiScene requires an initialized PeripheralManager")
        return peripheral_manager

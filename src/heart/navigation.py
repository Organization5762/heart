import dataclasses
from dataclasses import dataclass

import pygame
from lagom import Container

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.display.renderers.color import RenderColor
from heart.display.renderers.slide import SlideTransitionRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState


class AppController(BaseRenderer):
    def __init__(self) -> None:
        self.modes = GameModes()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.warmup = True
        super().__init__()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        self.modes.initialize(window, clock, peripheral_manager, orientation)
        super().initialize(window, clock, peripheral_manager, orientation)

    def get_renderers(self) -> list[BaseRenderer]:
        return self.modes.get_renderers()

    def add_sleep_mode(self) -> None:
        sleep_title = [
            SpritesheetLoop(
                sheet_file_path="kirby_sleep_64.png",
                metadata_file_path="kirby_sleep_64.json",
                image_scale=0.5,
                offset_y=-5,
                disable_input=True,
            ),
            TextRendering(
                text=["sleep"],
                font="Roboto",
                font_size=16,
                color=Color.kirby(),
                y_location=35,
            ),
        ]
        mode = self.add_mode(sleep_title)
        mode.add_renderer(RenderColor(Color(0, 0, 0)))

    def add_scene(self) -> "MultiScene":
        new_scene = MultiScene(scenes=[])
        title_renderer = TextRendering(
            text=["Untitled"],
            font="Roboto",
            font_size=14,
            color=Color(255, 105, 180),
        )
        self.modes.add_new_pages(title_renderer, new_scene)
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
        self.modes.add_new_pages(title_renderer, result)
        return result

    def is_empty(self) -> bool:
        return len(self.modes.state.renderers) == 0

@dataclass
class GameModeState:
    title_renderers: list[BaseRenderer] = dataclasses.field(default_factory=list)
    renderers: list[BaseRenderer] = dataclasses.field(default_factory=list)
    in_select_mode = True
    last_long_button_value = 0
    mode_offset = 0
    _active_mode_index = 0
    time_last_debugging_press = None

    previous_mode_index = 0
    sliding_transition = None

    def active_renderer(self) -> BaseRenderer:
        assert len(self.renderers) > 0, "Must have at least one renderer to select from"
        offset = (self._active_mode_index + self.mode_offset)
        mode_index = offset % len(self.renderers)
        last_scene_index = self.previous_mode_index

        if last_scene_index != mode_index:
            if self.mode_offset > 0:
                slide_dir = 1
            elif self.mode_offset < 0:
                slide_dir = -1
            else:
                forward_steps = (mode_index - last_scene_index) % len(self.renderers)
                backward_steps = (last_scene_index - mode_index) % len(self.renderers)
                slide_dir = 1 if forward_steps <= backward_steps else -1

            self.sliding_transition = SlideTransitionRenderer(
                renderer_A=self.title_renderers[last_scene_index],
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
            return self.title_renderers[mode_index]

        self.previous_mode_index = mode_index
        return self.renderers[mode_index]

class GameModes(AtomicBaseRenderer[GameModeState]):
    """GameModes represents a collection of modes in the game loop where different
    renderers can be added.

    Navigation is built-in to this, assuming the user long-presses

    """
    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> GameModeState:
        if self._state is not None:
            for renderer in self.state.renderers:
                renderer.initialize(window, clock, peripheral_manager, orientation)
            for renderer in self.state.title_renderers:
                renderer.initialize(window, clock, peripheral_manager, orientation)
            state = self._state
        else:
            state = GameModeState()
        peripheral_manager.get_main_switch_subscription().subscribe(
            on_next=self.handle_state
        )
        return state

    def add_new_pages(
        self, title_renderer: "BaseRenderer", renderers: "BaseRenderer"
    ) -> None:
        # TODO: Hack because we are trying to build and have state at the same time
        if self._state is None:
            self.set_state(GameModeState())
        self.state.renderers.append(renderers)
        self.state.title_renderers.append(title_renderer)

    def get_renderers(
        self
    ) -> list[BaseRenderer]:
        active_renderer = self.state.active_renderer()
        renderers = active_renderer.get_renderers()
        return renderers

    def real_process(self, window: pygame.Surface, clock: pygame.time.Clock, orientation: Orientation) -> None:
        for renderer in self.get_renderers():
            renderer.real_process(window=window, clock=clock, orientation=orientation)

    def handle_state(self, input: SwitchState) -> None:
        new_long_button_value = input.long_button_value
        if new_long_button_value != self.state.last_long_button_value:
            # Swap select modes
            if self.state.in_select_mode:
                
                # Combine the offset we're switching out of select mode
                self.state._active_mode_index += self.state.mode_offset
                self.state.mode_offset = 0
            else:
                # Switching to select mode, reset everything
                for renderer in self.state.renderers:
                    renderer.reset()

            self.state.in_select_mode = not self.state.in_select_mode
            self.state.last_long_button_value = new_long_button_value

        if self.state.in_select_mode:
            self.state.mode_offset = (
                input.rotation_since_last_long_button_press
            )


class ComposedRenderer(BaseRenderer):
    def __init__(self, renderers: list[BaseRenderer]) -> None:
        super().__init__()
        self.renderers: list[BaseRenderer] = renderers

    def get_renderers(
        self
    ) -> list[BaseRenderer]:
        result = []
        for renderer in self.renderers:
            result.extend(renderer.get_renderers())
        return result

    @property
    def name(self):
        name = "ComposedRenderer:"
        for renderer in self.renderers:
            name += f"{renderer.name}+"
        return name

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        for renderer in self.renderers:
            if renderer.warmup:
                renderer.initialize(window, clock, peripheral_manager, orientation)

    def add_renderer(self, *renderer: BaseRenderer):
        self.renderers.extend(renderer)

    def resolve_renderer(self, container: Container, renderer: type[BaseRenderer]):
        self.renderers.append(container.resolve(renderer))
    
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

    def reset(self) -> None:
        for renderer in self.renderers:
            renderer.reset()


@dataclass
class MultiSceneState:
    current_button_value: int = 0
    offset_of_button_value: int | None = None

class MultiScene(AtomicBaseRenderer[MultiSceneState]):
    def __init__(self, scenes: list[AtomicBaseRenderer]) -> None:
        super().__init__()
        self.scenes = scenes

    def get_renderers(
        self
    ) -> list[AtomicBaseRenderer]:
        index = (self.state.current_button_value - (self.state.offset_of_button_value or 0)) % len(self.scenes)
        return [
            *self.scenes[index].get_renderers()
        ]

    def _create_initial_state(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> MultiSceneState:
        state = MultiSceneState(
            current_button_value=0,
            offset_of_button_value=None
        )
        self.set_state(state)
        observable = peripheral_manager.get_main_switch_subscription()
        observable.subscribe(
            on_next=self._process_switch
        )

        for scene in self.scenes:
            scene.initialize(window, clock, peripheral_manager, orientation)

        return state

    def real_process(self, window: pygame.Surface, clock: pygame.time.Clock, orientation: Orientation) -> None:
        for render in self.get_renderers():
            render.real_process(window=window, clock=clock, orientation=orientation)

    def reset(self):
        self.state.offset_of_button_value = self.state.current_button_value
        return super().reset()

    def _process_switch(self, switch_value: SwitchState) -> None:
        self.state.current_button_value = switch_value.button_value
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.color import Color
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers import StatefulBaseRenderer
from heart.renderers.color import RenderColor
from heart.renderers.post_processing import (EdgePostProcessor,
                                             HueShiftPostProcessor,
                                             NullPostProcessor,
                                             SaturationPostProcessor)
from heart.renderers.slide_transition import \
    DEFAULT_GAUSSIAN_SIGMA as SLIDE_DEFAULT_GAUSSIAN_SIGMA
from heart.renderers.slide_transition import \
    DEFAULT_STATIC_MASK_STEPS as SLIDE_DEFAULT_STATIC_MASK_STEPS
from heart.renderers.slide_transition import SlideTransitionMode
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.text import TextRendering
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

if TYPE_CHECKING:
    from heart.renderers.slide_transition import SlideTransitionRenderer

    from .renderer_specs import RendererResolver
logger = get_logger(__name__)
DEFAULT_TRANSITION_MODE = SlideTransitionMode.SLIDE
DEFAULT_STATIC_MASK_STEPS = SLIDE_DEFAULT_STATIC_MASK_STEPS
DEFAULT_GAUSSIAN_SIGMA = SLIDE_DEFAULT_GAUSSIAN_SIGMA
INITIALIZATION_TEXT_COLOR = pygame.Color("white")
INITIALIZATION_BACKGROUND_COLOR = pygame.Color("black")
INITIALIZATION_TRACK_COLOR = pygame.Color(45, 45, 45)
INITIALIZATION_PROGRESS_COLOR = pygame.Color(255, 105, 180)
INITIALIZATION_TEXT_MARGIN_PX = 14
INITIALIZATION_BAR_HEIGHT_PX = 10
INITIALIZATION_BAR_MARGIN_PX = 18
INITIALIZATION_FONT_SIZE_PX = 24
INITIALIZATION_TERMINAL_BAR_WIDTH = 24


@dataclass
class ModeEntry:
    title_renderer: StatefulBaseRenderer
    renderer: StatefulBaseRenderer


@dataclass(frozen=True)
class GameModeInitializationContext:
    window: DisplayContext
    peripheral_manager: PeripheralManager
    orientation: Orientation


@dataclass
class GameModeState:
    entries: list[ModeEntry] = field(default_factory=list)
    post_processors: list[StatefulBaseRenderer] = field(default_factory=list)
    in_select_mode: bool = True
    last_long_button_value: int = 0
    mode_offset: int = 0
    _active_mode_index: int = 0
    previous_mode_index: int = 0
    sliding_transition: SlideTransitionRenderer | None = None
    transition_mode: SlideTransitionMode = DEFAULT_TRANSITION_MODE
    static_mask_steps: int = DEFAULT_STATIC_MASK_STEPS
    gaussian_sigma: float = DEFAULT_GAUSSIAN_SIGMA

    def active_renderer(self) -> StatefulBaseRenderer:
        assert len(self.entries) > 0, "Must have at least one renderer to select from"
        offset = self._active_mode_index + self.mode_offset
        mode_index = offset % len(self.entries)
        last_scene_index = self.previous_mode_index
        active_entry = self.entries[mode_index]
        previous_entry = self.entries[last_scene_index]

        if last_scene_index != mode_index:
            from heart.navigation import (  # avoids circular imports for patching
                SlideTransitionProvider, SlideTransitionRenderer)

            slide_dir = self._resolve_slide_direction(
                last_scene_index, mode_index, transition_mode=self.transition_mode
            )
            provider_kwargs: dict[str, object] = {}
            if self.transition_mode is not SlideTransitionMode.SLIDE:
                provider_kwargs["transition_mode"] = self.transition_mode
            if self.static_mask_steps != DEFAULT_STATIC_MASK_STEPS:
                provider_kwargs["static_mask_steps"] = self.static_mask_steps
            if self.gaussian_sigma != DEFAULT_GAUSSIAN_SIGMA:
                provider_kwargs["gaussian_sigma"] = self.gaussian_sigma
            provider = SlideTransitionProvider(
                renderer_a=previous_entry.title_renderer,
                renderer_b=active_entry.title_renderer,
                direction=slide_dir,
                **provider_kwargs,
            )
            self.sliding_transition = SlideTransitionRenderer(provider)
            self.previous_mode_index = mode_index
            return self.sliding_transition

        if self.sliding_transition is not None:
            if self.sliding_transition.is_done():
                self.sliding_transition = None
            else:
                return self.sliding_transition

        if self.in_select_mode:
            return active_entry.title_renderer

        self.previous_mode_index = mode_index
        return active_entry.renderer

    def _resolve_slide_direction(
        self,
        last_scene_index: int,
        mode_index: int,
        *,
        transition_mode: SlideTransitionMode,
    ) -> int:
        if transition_mode in (SlideTransitionMode.STATIC, SlideTransitionMode.GAUSSIAN):
            return 0
        if self.mode_offset > 0:
            return 1
        if self.mode_offset < 0:
            return -1
        forward_steps = (mode_index - last_scene_index) % len(self.entries)
        backward_steps = (last_scene_index - mode_index) % len(self.entries)
        return 1 if forward_steps <= backward_steps else -1


class GameModes(StatefulBaseRenderer[GameModeState]):
    """GameModes represents a collection of modes in the game loop where different
    renderers can be added.

    Navigation is built-in to this, assuming the user long-presses.
    """

    def __init__(self, renderer_resolver: "RendererResolver" | None = None) -> None:
        super().__init__()
        self._initialization_context: GameModeInitializationContext | None = None
        self._renderer_resolver = renderer_resolver
        # TODO: Fix this wonkiness
        self.device_display_mode = None

    def _internal_device_display_mode(self) -> DeviceDisplayMode:
        renderers = [
            *[entry.renderer for entry in self.state.entries],
            *[entry.title_renderer for entry in self.state.entries],
        ]
        if any(
            renderer.device_display_mode == DeviceDisplayMode.OPENGL
            for renderer in renderers
        ):
            return DeviceDisplayMode.OPENGL
        return DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> GameModeState:
        self._initialization_context = GameModeInitializationContext(
            window=window,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        if self._state is not None:
            self._initialize_registered_renderers(
                window, peripheral_manager, orientation
            )
            state = self._state
        else:
            state = GameModeState()
        if not state.post_processors:
            state.post_processors.extend(self._default_post_processors())
        peripheral_manager.navigation_profile.browse_delta.subscribe(
            on_next=self._handle_browse_delta,
        )
        peripheral_manager.navigation_profile.activate.subscribe(
            on_next=self._handle_activate,
        )
        peripheral_manager.navigation_profile.alternate_activate.subscribe(
            on_next=self._handle_alternate_activate,
        )
        return state

    def _register_mode(
        self,
        title_renderer: StatefulBaseRenderer,
        renderer: StatefulBaseRenderer,
    ) -> None:
        if self._state is None:
            self.set_state(GameModeState())
        self.state.entries.append(
            ModeEntry(title_renderer=title_renderer, renderer=renderer)
        )
        if self.is_initialized() and self._initialization_context is not None:
            title_renderer.initialize(
                self._initialization_context.window,
                self._initialization_context.peripheral_manager,
                self._initialization_context.orientation,
            )
            renderer.initialize(
                self._initialization_context.window,
                self._initialization_context.peripheral_manager,
                self._initialization_context.orientation,
            )

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
                font="Grand9K Pixel.ttf",
                font_size=16,
                color=Color.kirby(),
                y_location=0.55,
            ),
        ]
        mode = self.add_mode(sleep_title)
        mode.add_renderer(RenderColor(Color(0, 0, 0)))

    def add_scene(self):
        from .multi_scene import MultiScene

        new_scene = MultiScene(
            scenes=[],
            renderer_resolver=self._renderer_resolver,
        )
        title_renderer = self._build_title_renderer("Untitled")
        self._register_mode(title_renderer, new_scene)
        return new_scene

    def add_mode(
        self,
        title: str
        | list[StatefulBaseRenderer | type[StatefulBaseRenderer]]
        | type[StatefulBaseRenderer]
        | StatefulBaseRenderer
        | None = None,
    ):
        from .composed_renderer import ComposedRenderer

        result = ComposedRenderer(
            renderers=[],
            renderer_resolver=self._renderer_resolver,
        )
        if title is None:
            title = "Untitled"

        title_renderer = self._build_title_renderer(title)
        self._register_mode(title_renderer, result)
        return result

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        active_renderer = self.state.active_renderer()
        return active_renderer.get_renderers()

    def get_post_processors(self) -> list[StatefulBaseRenderer]:
        return list(self.state.post_processors)

    def is_empty(self) -> bool:
        return len(self.state.entries) == 0

    def real_process(
        self, window: DisplayContext, orientation: Orientation
    ) -> None:
        raise NotImplementedError("GameModes.real_process is not implemented")

    def handle_state(self, input: SwitchState) -> None:
        new_long_button_value = input.long_button_value
        if new_long_button_value != self.state.last_long_button_value:
            if self.state.in_select_mode:
                self.state._active_mode_index += self.state.mode_offset
                self.state.mode_offset = 0
            else:
                for entry in self.state.entries:
                    entry.renderer.reset()
                for renderer in self.state.post_processors:
                    renderer.reset()

            self.state.in_select_mode = not self.state.in_select_mode
            self.state.last_long_button_value = new_long_button_value

        if self.state.in_select_mode:
            self.state.mode_offset = input.rotation_since_last_long_button_press

    def _handle_browse_delta(self, delta: int) -> None:
        if not self.state.in_select_mode or delta == 0:
            return
        self.state.mode_offset += delta

    def _handle_activate(self, _event: object) -> None:
        if not self.state.in_select_mode:
            return
        self.state._active_mode_index += self.state.mode_offset
        self.state.mode_offset = 0
        self.state.in_select_mode = False

    def _handle_alternate_activate(self, _event: object) -> None:
        if self.state.in_select_mode:
            return
        for entry in self.state.entries:
            entry.renderer.reset()
        for renderer in self.state.post_processors:
            renderer.reset()
        self.state.in_select_mode = True

    def _initialize_registered_renderers(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        initialization_renderers = self._initialization_renderers()
        total_renderers = len(initialization_renderers)
        self._render_initialization_progress(window, completed=0, total=total_renderers)

        # Renderers may have different display modes, so we need to initialize them all.
        for completed, renderer in enumerate(initialization_renderers, start=1):
            try:
                with window.display_mode(renderer.device_display_mode):
                    renderer.initialize(window, peripheral_manager, orientation)
            except Exception:
                logger.exception(
                    "Failed to initialize renderer %s",
                    renderer.name,
                )
                raise
            self._render_initialization_progress(
                window,
                completed=completed,
                total=total_renderers,
            )

    def _initialization_renderers(self) -> list[StatefulBaseRenderer]:
        return [
            *[entry.title_renderer for entry in self.state.entries],
            *[entry.renderer for entry in self.state.entries],
            *self.state.post_processors,
        ]

    def _render_initialization_progress(
        self,
        window: DisplayContext,
        *,
        completed: int,
        total: int,
    ) -> None:
        if total <= 0:
            return
        self._log_initialization_progress(completed=completed, total=total)
        if window.screen is None:
            return
        if window.screen.get_flags() & pygame.OPENGL:
            return

        screen = window.screen
        screen_width, screen_height = screen.get_size()
        progress_ratio = completed / total
        bar_width = max(1, screen_width - (INITIALIZATION_BAR_MARGIN_PX * 2))
        bar_top = screen_height - INITIALIZATION_BAR_MARGIN_PX - INITIALIZATION_BAR_HEIGHT_PX
        progress_width = int(bar_width * progress_ratio)

        screen.fill(INITIALIZATION_BACKGROUND_COLOR)

        if not pygame.font.get_init():
            pygame.font.init()
        font = pygame.font.Font(None, INITIALIZATION_FONT_SIZE_PX)
        label = f"Initializing game mode renderers ({completed} of {total})"
        text_surface = font.render(label, True, INITIALIZATION_TEXT_COLOR)
        text_rect = text_surface.get_rect()
        text_rect.midbottom = (
            screen_width // 2,
            bar_top - INITIALIZATION_TEXT_MARGIN_PX,
        )
        screen.blit(text_surface, text_rect)

        track_rect = pygame.Rect(
            INITIALIZATION_BAR_MARGIN_PX,
            bar_top,
            bar_width,
            INITIALIZATION_BAR_HEIGHT_PX,
        )
        pygame.draw.rect(screen, INITIALIZATION_TRACK_COLOR, track_rect, border_radius=4)

        if progress_width > 0:
            progress_rect = pygame.Rect(
                INITIALIZATION_BAR_MARGIN_PX,
                bar_top,
                progress_width,
                INITIALIZATION_BAR_HEIGHT_PX,
            )
            pygame.draw.rect(
                screen,
                INITIALIZATION_PROGRESS_COLOR,
                progress_rect,
                border_radius=4,
            )

        pygame.display.flip()

    def _log_initialization_progress(self, *, completed: int, total: int) -> None:
        progress_units = max(0, min(completed, total))
        filled_units = int(
            (progress_units / total) * INITIALIZATION_TERMINAL_BAR_WIDTH
        )
        bar = (
            ("#" * filled_units)
            + ("-" * (INITIALIZATION_TERMINAL_BAR_WIDTH - filled_units))
        )
        logger.info(
            "Initializing game mode renderers (%s of %s) [%s]",
            completed,
            total,
            bar,
        )

    @staticmethod
    def _default_post_processors() -> list[StatefulBaseRenderer]:
        return [
            SaturationPostProcessor(),
            HueShiftPostProcessor(),
            EdgePostProcessor(),
            NullPostProcessor(),
        ]

    def _build_title_renderer(
        self,
        title: str
        | list[StatefulBaseRenderer | type[StatefulBaseRenderer]]
        | type[StatefulBaseRenderer]
        | StatefulBaseRenderer,
    ) -> StatefulBaseRenderer:
        from .composed_renderer import ComposedRenderer

        if isinstance(title, str):
            return TextRendering(
                text=[title],
                font="Grand9K Pixel.ttf",
                font_size=12,
                color=Color(255, 105, 180),
                y_location=0.5,
            )
        if isinstance(title, list):
            composed = ComposedRenderer(
                renderers=[],
                renderer_resolver=self._renderer_resolver,
            )
            composed.add_renderer(*title)
            return composed
        if isinstance(title, type) and issubclass(title, StatefulBaseRenderer):
            if self._renderer_resolver is None:
                raise ValueError("GameModes requires a renderer resolver")
            return self._renderer_resolver.resolve(title)
        if isinstance(title, StatefulBaseRenderer):
            return title
        raise ValueError(f"Title must be a string or StatefulBaseRenderer, got: {title}")

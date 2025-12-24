import time
from dataclasses import replace
from typing import Any, Callable, Generic, TypeVar, final

import pygame
from reactivex import Observable
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.device import Layout, Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.state_provider import ImmutableStateProvider
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseRenderer:
    @property
    def name(self):
        return self.__class__.__name__

    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.warmup = True
        self._surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._tiled_surface_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._tile_positions_cache: dict[tuple[int, int, int, int], list[tuple[int, int]]] = {}

    def is_initialized(self) -> bool:
        return self.initialized

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # We call process once incase there is any implicit cachable work to do
        # e.g. for numba jitted functions we'll cache their compiled code
        if self.warmup:
            screen = self._get_input_screen(window, orientation)
            self.process(screen, clock, peripheral_manager, orientation)
        self.initialized = True

    def reset(self):
        pass

    def get_renderers(
        self
    ) -> list["BaseRenderer"]:
        return [self]

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        window_x, window_y = window.get_size()

        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL | DeviceDisplayMode.OPENGL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)
        if Configuration.render_surface_cache_enabled():
            cached = self._surface_cache.get(screen_size)
            if cached is None:
                cached = pygame.Surface(screen_size, pygame.SRCALPHA)
                self._surface_cache[screen_size] = cached
            else:
                cached.fill((0, 0, 0, 0))
            return cached
        return pygame.Surface(screen_size, pygame.SRCALPHA)

    def _postprocess_input_screen(
        self, screen: pygame.Surface, orientation: Orientation
    ):
        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen = self._tile_surface(
                    screen=screen, rows=layout.rows, cols=layout.columns
                )
            case DeviceDisplayMode.FULL:
                pass
        return screen

    def _internal_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if not self.is_initialized():
            self.initialize(window, clock, peripheral_manager, orientation)

        screen = self._get_input_screen(window, orientation)
        start_ns = time.perf_counter_ns()
        self.process(screen, clock, peripheral_manager, orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))
        logger.debug(
            "renderer.frame",  # structured logging friendly key
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
            },
        )

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        pass

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        target_size = (tile_width * cols, tile_height * rows)
        if Configuration.render_surface_cache_enabled():
            cache_key = (tile_width, tile_height, rows, cols)
            tiled_surface = self._tiled_surface_cache.get(cache_key)
            if tiled_surface is None:
                tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)
                self._tiled_surface_cache[cache_key] = tiled_surface
            else:
                tiled_surface.fill((0, 0, 0, 0))
        else:
            tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)

        if Configuration.render_tile_strategy() == "blits":
            positions_key = (tile_width, tile_height, rows, cols)
            positions = self._tile_positions_cache.get(positions_key)
            if positions is None:
                positions = [
                    (col * tile_width, row * tile_height)
                    for row in range(rows)
                    for col in range(cols)
                ]
                self._tile_positions_cache[positions_key] = positions
            tiled_surface.blits([(screen, pos) for pos in positions])
            return tiled_surface

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface

StateT = TypeVar("StateT")


class AtomicBaseRenderer(Generic[StateT]):
    """Base renderer that manages an immutable state snapshot."""
    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.warmup = True
        self._state: StateT | None = None
        self._surface_cache: dict[tuple[int, int], pygame.Surface] = {}
        self._tiled_surface_cache: dict[tuple[int, int, int, int], pygame.Surface] = {}
        self._tile_positions_cache: dict[tuple[int, int, int, int], list[tuple[int, int]]] = {}

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation
    ) -> StateT:
        raise NotImplementedError

    @final
    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # We call process once incase there is any implicit cachable work to do
        # e.g. for numba jitted functions we'll cache their compiled code
        self._state = self._create_initial_state(window=window, clock=clock, peripheral_manager=peripheral_manager, orientation=orientation)
        try:
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
        except Exception as e:
            logger.warning(f"Error initializing renderer ({type(self)}): {e}")
            raise e
        self.initialized = True

    @property
    def state(self) -> StateT:
        assert self._state is not None
        return self._state

    def set_state(self, state: StateT) -> None:
        self._state = state

    def update_state(self, **changes: Any) -> None:
        assert self._state is not None
        self._state = replace(self._state, **changes)

    def mutate_state(self, mutator: Callable[[StateT], StateT]) -> None:
        assert self._state is not None
        self._state = mutator(self._state)

    @property
    def name(self):
        return self.__class__.__name__

    def is_initialized(self) -> bool:
        return self.initialized

    def get_renderers(
        self
    ) -> list["StatefulBaseRenderer"]:
        return self._real_get_renderers()

    def _real_get_renderers(
        self
    ) -> list["StatefulBaseRenderer"]:
        return [self]

    @final
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        return self.real_process(
            window=window,
            clock=clock,
            orientation=orientation
        )

    
    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        raise NotImplementedError("Please implement")


    def _postprocess_input_screen(
        self, screen: pygame.Surface, orientation: Orientation
    ):
        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen = self._tile_surface(
                    screen=screen, rows=layout.rows, cols=layout.columns
                )
            case DeviceDisplayMode.FULL:
                pass
        return screen


    @final
    def _internal_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        return self._real_internal_process(
            window=window,
            clock=clock,
            orientation=orientation
        )

    def _real_internal_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        if not self.is_initialized():
            raise ValueError("Needs to be initialized")

        screen = self._get_input_screen(window, orientation)
        start_ns = time.perf_counter_ns()
        self.real_process(window=screen, clock=clock, orientation=orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))
        logger.debug(
            "renderer.frame",
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
            },
        )

    def reset(self):
        pass

    ##
    # Base helper gore
    ##
    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        window_x, window_y = window.get_size()

        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL | DeviceDisplayMode.OPENGL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)
        if Configuration.render_surface_cache_enabled():
            cached = self._surface_cache.get(screen_size)
            if cached is None:
                cached = pygame.Surface(screen_size, pygame.SRCALPHA)
                self._surface_cache[screen_size] = cached
            else:
                cached.fill((0, 0, 0, 0))
            return cached
        return pygame.Surface(screen_size, pygame.SRCALPHA)

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        target_size = (tile_width * cols, tile_height * rows)
        if Configuration.render_surface_cache_enabled():
            cache_key = (tile_width, tile_height, rows, cols)
            tiled_surface = self._tiled_surface_cache.get(cache_key)
            if tiled_surface is None:
                tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)
                self._tiled_surface_cache[cache_key] = tiled_surface
            else:
                tiled_surface.fill((0, 0, 0, 0))
        else:
            tiled_surface = pygame.Surface(target_size, pygame.SRCALPHA)

        if Configuration.render_tile_strategy() == "blits":
            positions_key = (tile_width, tile_height, rows, cols)
            positions = self._tile_positions_cache.get(positions_key)
            if positions is None:
                positions = [
                    (col * tile_width, row * tile_height)
                    for row in range(rows)
                    for col in range(cols)
                ]
                self._tile_positions_cache[positions_key] = positions
            tiled_surface.blits([(screen, pos) for pos in positions])
            return tiled_surface

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface

class StatefulBaseRenderer(AtomicBaseRenderer[StateT], Generic[StateT]):
    def __init__(
        self,
        builder: ObservableProvider[StateT] | None = None,
        *args,
        state: StateT | None = None,
        **kwargs,
    ) -> None:
        if builder is not None and state is not None:
            raise ValueError("StatefulBaseRenderer expects either builder or state")
        if builder is None and state is not None:
            builder = ImmutableStateProvider(state)
        self.builder = builder
        self._subscription: Disposable | None = None
        super().__init__(*args, **kwargs)

    def state_observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> Observable[StateT]:
        assert self.builder is not None
        return self.builder.observable()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self.builder is not None:
            observable = self.state_observable(
                peripheral_manager=peripheral_manager,
            )
            self._subscription = observable.subscribe(on_next=self.set_state)
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
            self.initialized = True
            return

        if not hasattr(self, "_create_initial_state"):
            msg = "StatefulBaseRenderer requires a builder or _create_initial_state"
            raise ValueError(msg)

        state = self._create_initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
        self.set_state(state)
        if self.warmup:
            screen = self._get_input_screen(window, orientation)
            self.process(screen, clock, peripheral_manager, orientation)
        self.initialized = True

    def reset(self):
        if self._subscription is not None:
            self._subscription.dispose()
            self._subscription = None
        super().reset()

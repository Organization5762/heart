import time
from dataclasses import replace
from typing import Any, Callable, Generic, TypeVar, final

import pygame
from reactivex import Observable
from reactivex.disposable import Disposable

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import (ObservableProvider,
                                             StaticStateProvider)
from heart.renderers.surface_cache import RendererSurfaceCache
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
        self._surface_cache = RendererSurfaceCache()

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

    def get_renderers(self) -> list["BaseRenderer"]:
        return [self]

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        return self._surface_cache.get_input_screen(
            window=window,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

    def _postprocess_input_screen(
        self, screen: pygame.Surface, orientation: Orientation
    ):
        return self._surface_cache.postprocess_input_screen(
            screen=screen,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

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
        return self._surface_cache.tile_surface(screen=screen, rows=rows, cols=cols)


StateT = TypeVar("StateT")


class AtomicBaseRenderer(Generic[StateT]):
    """Base renderer that manages an immutable state snapshot."""

    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.warmup = True
        self._state: StateT | None = None
        self._surface_cache = RendererSurfaceCache()

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
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
        self._state = self._create_initial_state(
            window=window,
            clock=clock,
            peripheral_manager=peripheral_manager,
            orientation=orientation,
        )
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

    def get_renderers(self) -> list["StatefulBaseRenderer"]:
        return self._real_get_renderers()

    def _real_get_renderers(self) -> list["StatefulBaseRenderer"]:
        return [self]

    @final
    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        return self.real_process(window=window, clock=clock, orientation=orientation)

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
        return self._surface_cache.postprocess_input_screen(
            screen=screen,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

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
            orientation=orientation,
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

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        return self._surface_cache.get_input_screen(
            window=window,
            orientation=orientation,
            display_mode=self.device_display_mode,
        )

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        return self._surface_cache.tile_surface(screen=screen, rows=rows, cols=cols)


class StatefulBaseRenderer(AtomicBaseRenderer[StateT], Generic[StateT]):
    def __init__(
        self,
        builder: ObservableProvider[StateT] | None = None,
        state: StateT | None = None,
        *args,
        **kwargs,
    ) -> None:
        if builder is not None and state is not None:
            raise ValueError("StatefulBaseRenderer accepts a builder or state, not both")

        if builder is None and state is not None:
            builder = StaticStateProvider(state)

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

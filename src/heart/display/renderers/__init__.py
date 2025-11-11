import time
from dataclasses import dataclass, replace
from typing import Any, Callable, Generic, TypeVar

import pygame

from heart import DeviceDisplayMode
from heart.device import Layout, Orientation
from heart.display.renderers.internal import FrameAccumulator
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class BaseRenderer:
    supports_frame_accumulator: bool = False

    @property
    def name(self):
        return self.__class__.__name__

    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.initialized = False
        self.warmup = True
        self._subscription_factories: list[
            Callable[[PeripheralManager], Callable[[], None] | None]
        ] = []
        self._active_unsubscribers: list[Callable[[], None]] = []
        self._subscriptions_active = False
        self._subscription_context: PeripheralManager | None = None
        self._switch_state_cache: SwitchState | None = None
        self._switch_state_cache_enabled = False

    def is_initialized(self) -> bool:
        return self.initialized

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.ensure_input_bindings(peripheral_manager)
        # We call process once incase there is any implicit cachable work to do
        # e.g. for numba jitted functions we'll cache their compiled code
        try:
            if self.warmup:
                screen = self._get_input_screen(window, orientation)
                self.process(screen, clock, peripheral_manager, orientation)
        except Exception as e:
            logger.warning(f"Error initializing renderer ({type(self)}): {e}")
        self.initialized = True

    def reset(self):
        self._switch_state_cache = None

    def get_renderers(
        self, peripheral_manager: PeripheralManager
    ) -> list["BaseRenderer"]:
        self.ensure_input_bindings(peripheral_manager)
        return [self]

    def _get_input_screen(self, window: pygame.Surface, orientation: Orientation):
        window_x, window_y = window.get_size()

        match self.device_display_mode:
            case DeviceDisplayMode.MIRRORED:
                layout: Layout = orientation.layout
                screen_size = (window_x // layout.columns, window_y // layout.rows)
            case DeviceDisplayMode.FULL:
                # The screen is the full size of the device
                screen_size = (window_x, window_y)
            case DeviceDisplayMode.OPENGL:
                # todo: this is actually completely unused for this dispaly mode
                #  so there's some smell here but providing this dummy val for now
                screen_size = (window_x, window_y)
        screen = pygame.Surface(screen_size, pygame.SRCALPHA)
        return screen

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
        if self.supports_frame_accumulator:
            accumulator = FrameAccumulator.from_surface(screen)
            self.process_with_accumulator(
                accumulator, clock, peripheral_manager, orientation
            )
            screen = accumulator.flush(screen)
        else:
            self.process(screen, clock, peripheral_manager, orientation)
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        screen = self._postprocess_input_screen(screen, orientation)

        window.blit(screen, (0, 0))
        logger.debug(
            "renderer.frame",  # structured logging friendly key
            extra={
                "renderer": self.name,
                "duration_ms": duration_ms,
                "uses_accumulator": self.supports_frame_accumulator,
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

    def process_with_accumulator(
        self,
        accumulator: FrameAccumulator,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Render into a :class:`FrameAccumulator` (optional override)."""

        self.process(accumulator.surface, clock, peripheral_manager, orientation)

    # ------------------------------------------------------------------
    # Subscription helpers
    # ------------------------------------------------------------------
    def ensure_input_bindings(self, peripheral_manager: PeripheralManager) -> None:
        """Ensure event and peripheral subscriptions are active for ``self``."""

        self._activate_managed_subscriptions(peripheral_manager)

    def detach_input_bindings(self) -> None:
        """Remove active subscriptions registered via helper APIs."""

        self._cleanup_managed_subscriptions()

    def register_event_listener(
        self,
        event_type: str,
        callback: Callable[[Input], None],
        *,
        priority: int = 0,
    ) -> None:
        """Register ``callback`` for ``event_type`` on the manager event bus."""

        def factory(
            peripheral_manager: PeripheralManager,
        ) -> Callable[[], None] | None:
            bus: EventBus | None = getattr(peripheral_manager, "event_bus", None)
            if bus is None:
                logger.debug(
                    "Renderer %s missing event bus; subscription to %s skipped",
                    self.name,
                    event_type,
                )
                return None
            handle = bus.subscribe(event_type, callback, priority=priority)

            def unsubscribe() -> None:
                try:
                    bus.unsubscribe(handle)
                except Exception:
                    logger.exception(
                        "Renderer %s failed to unsubscribe from %s",
                        self.name,
                        event_type,
                    )

            return unsubscribe

        self._register_managed_subscription(factory)

    def register_switch_state_callback(
        self,
        callback: Callable[[SwitchState], None],
        *,
        replay: bool = True,
    ) -> None:
        """Subscribe ``callback`` to primary switch state updates."""

        def factory(
            peripheral_manager: PeripheralManager,
        ) -> Callable[[], None] | None:
            def _dispatch(state: SwitchState) -> None:
                try:
                    callback(state)
                except Exception:
                    logger.exception(
                        "Renderer %s switch callback failed", self.name
                    )

            try:
                unsubscribe = peripheral_manager.subscribe_main_switch(_dispatch)
            except Exception:
                logger.debug(
                    "Renderer %s could not subscribe to main switch", self.name,
                    exc_info=True,
                )
                return None

            if replay:
                try:
                    initial_state = peripheral_manager.get_main_switch_state()
                except Exception:
                    logger.debug(
                        "Renderer %s could not fetch initial switch state", self.name,
                        exc_info=True,
                    )
                else:
                    _dispatch(initial_state)

            return unsubscribe

        self._register_managed_subscription(factory)

    def enable_switch_state_cache(self, *, replay: bool = True) -> None:
        """Cache switch state updates and expose :meth:`get_switch_state`."""

        self._switch_state_cache_enabled = True

        def _update(state: SwitchState) -> None:
            self._switch_state_cache = state
            try:
                self.on_switch_state(state)
            except Exception:
                logger.exception(
                    "Renderer %s failed inside on_switch_state", self.name
                )

        self.register_switch_state_callback(_update, replay=replay)

    def get_switch_state(self) -> SwitchState:
        """Return the most recently cached main switch state."""

        if not self._switch_state_cache_enabled or self._switch_state_cache is None:
            raise RuntimeError("Switch state has not been initialized")
        return self._switch_state_cache

    def on_switch_state(self, state: SwitchState) -> None:
        """Hook executed when :meth:`enable_switch_state_cache` receives updates."""

    def _register_managed_subscription(
        self,
        factory: Callable[[PeripheralManager], Callable[[], None] | None],
    ) -> None:
        self._subscription_factories.append(factory)
        if self._subscription_context is not None:
            try:
                unsubscribe = factory(self._subscription_context)
            except Exception:
                logger.exception(
                    "Renderer %s failed to register subscription immediately",
                    self.name,
                )
            else:
                if unsubscribe is not None:
                    self._active_unsubscribers.append(unsubscribe)
                    self._subscriptions_active = True

    def _activate_managed_subscriptions(
        self, peripheral_manager: PeripheralManager
    ) -> None:
        if (
            self._subscriptions_active
            and self._subscription_context is peripheral_manager
        ):
            return
        if self._subscriptions_active:
            self._cleanup_managed_subscriptions()
        self._subscription_context = peripheral_manager
        for factory in self._subscription_factories:
            try:
                unsubscribe = factory(peripheral_manager)
            except Exception:
                logger.exception(
                    "Renderer %s failed to activate subscription", self.name
                )
                continue
            if unsubscribe is not None:
                self._active_unsubscribers.append(unsubscribe)
        self._subscriptions_active = True

    def _cleanup_managed_subscriptions(self) -> None:
        if not self._active_unsubscribers:
            self._subscriptions_active = False
            self._subscription_context = None
            return
        for unsubscribe in self._active_unsubscribers:
            try:
                unsubscribe()
            except Exception:
                logger.exception(
                    "Renderer %s failed while detaching subscription", self.name
                )
        self._active_unsubscribers.clear()
        self._subscriptions_active = False
        self._subscription_context = None

    def _tile_surface(
        self, screen: pygame.Surface, rows: int, cols: int
    ) -> pygame.Surface:
        tile_width, tile_height = screen.get_size()
        tiled_surface = pygame.Surface(
            (tile_width * cols, tile_height * rows), pygame.SRCALPHA
        )

        for row in range(rows):
            for col in range(cols):
                dest_pos = (col * tile_width, row * tile_height)
                tiled_surface.blit(screen, dest_pos)

        return tiled_surface


StateT = TypeVar("StateT")


class AtomicBaseRenderer(BaseRenderer, Generic[StateT]):
    """Base renderer that manages an immutable state snapshot."""

    def __init__(self) -> None:
        super().__init__()
        self._state: StateT = self._create_initial_state()

    def _create_initial_state(self) -> StateT:
        raise NotImplementedError

    @property
    def state(self) -> StateT:
        return self._state

    def set_state(self, state: StateT) -> None:
        self._state = state

    def update_state(self, **changes: Any) -> None:
        self._state = replace(self._state, **changes)

    def mutate_state(self, mutator: Callable[[StateT], StateT]) -> None:
        self._state = mutator(self._state)

    def reset(self) -> None:
        super().reset()
        self._state = self._create_initial_state()


@dataclass
class KeyFrame:
    frame: tuple[int, int, int, int]
    up: int = 0
    down: int = 0
    left: int = 0
    right: int = 0

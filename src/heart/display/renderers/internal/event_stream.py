"""Utilities for bridging renderer output through the event bus."""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

import pygame

from heart.display.renderers import AtomicBaseRenderer, BaseRenderer
from heart.events.types import RendererFrame
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus, SubscriptionHandle
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class RendererEventPublisherState:
    sequence: int = 0


class RendererEventPublisher(AtomicBaseRenderer[RendererEventPublisherState]):
    """Wrap a renderer and publish its frames onto the event bus."""

    def __init__(
        self,
        renderer: BaseRenderer,
        *,
        channel: str,
        producer_id: int | None = None,
        pixel_format: str = "RGBA",
        metadata_factory: Callable[[pygame.Surface], Mapping[str, Any]] | None = None,
    ) -> None:
        AtomicBaseRenderer.__init__(self)
        if not channel:
            raise ValueError("RendererEventPublisher channel must be provided")
        self._renderer = renderer
        self._channel = channel
        self._producer_id = producer_id if producer_id is not None else id(renderer)
        self._pixel_format = pixel_format
        self._metadata_factory = metadata_factory

        # Mirror display configuration so upstream sizing remains accurate.
        self.device_display_mode = renderer.device_display_mode
        self.supports_frame_accumulator = renderer.supports_frame_accumulator

    def reset(self) -> None:
        self._renderer.reset()
        super().reset()

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation,
    ) -> None:
        self._renderer._internal_process(window, clock, peripheral_manager, orientation)
        bus = getattr(peripheral_manager, "event_bus", None)
        if bus is None:
            _LOGGER.debug(
                "RendererEventPublisher dropped frame; manager missing event bus",
            )
            return
        metadata: Mapping[str, Any] | None = None
        if self._metadata_factory is not None:
            try:
                metadata = dict(self._metadata_factory(window))
            except Exception:  # pragma: no cover - defensive logging only
                _LOGGER.exception("RendererEventPublisher metadata_factory failed")
        frame = RendererFrame.from_surface(
            self._channel,
            window,
            renderer=self._renderer.name,
            frame_id=self.state.sequence,
            pixel_format=self._pixel_format,
            metadata=metadata,
        )
        self.update_state(sequence=self.state.sequence + 1)
        bus.emit(frame.to_input(producer_id=self._producer_id))

    def _create_initial_state(self) -> RendererEventPublisherState:
        return RendererEventPublisherState()


@dataclass(frozen=True)
class RendererEventSubscriberState:
    latest_surface: pygame.Surface | None = None
    target_size: tuple[int, int] | None = None
    has_frame: bool = False


class RendererEventSubscriber(AtomicBaseRenderer[RendererEventSubscriberState]):
    """Render the latest :class:`RendererFrame` observed on the event bus."""

    def __init__(
        self,
        *,
        channel: str,
        producer_id: int | None = None,
        priority: int = 0,
    ) -> None:
        AtomicBaseRenderer.__init__(self)
        if not channel:
            raise ValueError("RendererEventSubscriber channel must be provided")
        self._channel = channel
        self._producer_id = producer_id
        self._priority = priority
        self._subscription: SubscriptionHandle | None = None
        self._event_bus: EventBus | None = None
        self._frame_lock = threading.Lock()

    def reset(self) -> None:
        if self._event_bus is not None and self._subscription is not None:
            try:
                self._event_bus.unsubscribe(self._subscription)
            except Exception:  # pragma: no cover - defensive logging only
                _LOGGER.exception("Failed to unsubscribe renderer event subscriber")
        self._subscription = None
        self._event_bus = None
        super().reset()

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation,
    ) -> None:
        self.update_state(target_size=window.get_size())
        self._ensure_subscription(peripheral_manager)
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation,
    ) -> None:
        if self._subscription is None:
            self._ensure_subscription(peripheral_manager)
        with self._frame_lock:
            surface = (
                self.state.latest_surface.copy()
                if self.state.latest_surface is not None
                else None
            )
        if surface is None:
            return
        window.blit(surface, (0, 0))

    def has_frame(self) -> bool:
        """Return ``True`` when at least one frame has been observed."""

        with self._frame_lock:
            return self.state.has_frame

    def peek_latest_surface(self) -> pygame.Surface | None:
        """Return a copy of the most recent frame without mutating state."""

        with self._frame_lock:
            surface = self.state.latest_surface
            if surface is None:
                return None
            return surface.copy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_subscription(self, peripheral_manager: PeripheralManager) -> None:
        if self._subscription is not None:
            return
        bus = getattr(peripheral_manager, "event_bus", None)
        if bus is None:
            _LOGGER.debug(
                "RendererEventSubscriber missing event bus; rendering will stall",
            )
            return
        self._event_bus = bus
        self._subscription = bus.subscribe(
            RendererFrame.EVENT_TYPE,
            self._handle_frame,
            priority=self._priority,
        )

    def _handle_frame(self, event: Input) -> None:
        payload = event.data
        if not isinstance(payload, RendererFrame):
            return
        if payload.channel != self._channel:
            return
        if self._producer_id is not None and event.producer_id != self._producer_id:
            return
        surface = payload.to_surface()
        target_size = self.state.target_size
        if target_size and surface.get_size() != target_size:
            surface = pygame.transform.smoothscale(surface, target_size)
        with self._frame_lock:
            self.update_state(latest_surface=surface, has_frame=True)

    def _create_initial_state(self) -> RendererEventSubscriberState:
        return RendererEventSubscriberState()


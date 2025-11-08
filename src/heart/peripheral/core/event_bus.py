"""Local event bus for reactive peripheral integrations."""

from __future__ import annotations

import abc
import logging
import threading
import uuid
from collections import defaultdict, deque
from collections.abc import Mapping as MappingABC
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
from types import MappingProxyType
from typing import (Any, Callable, Deque, Iterable, List, Mapping,
                    MutableMapping, Optional, Sequence)

from . import Input
from .state_store import StateStore

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "EventBus",
    "EventPlaylist",
    "EventPlaylistManager",
    "PlaylistHandle",
    "PlaylistStep",
    "SequenceMatcher",
    "SubscriptionHandle",
    "VirtualPeripheralContext",
    "VirtualPeripheralDefinition",
    "VirtualPeripheralHandle",
    "VirtualPeripheralManager",
    "gated_mirror_virtual_peripheral",
    "gated_playlist_virtual_peripheral",
    "double_tap_virtual_peripheral",
    "sequence_virtual_peripheral",
    "simultaneous_virtual_peripheral",
]


EventCallback = Callable[[Input], None]
GatePredicate = Callable[["VirtualPeripheralContext", Input], bool]


def _clone_payload(value: Any) -> Any:
    """Return a defensive copy of ``value`` suitable for reuse."""

    if isinstance(value, MappingABC):
        return {key: _clone_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clone_payload(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_clone_payload(item) for item in value)
    if isinstance(value, set):
        return {_clone_payload(item) for item in value}
    if isinstance(value, frozenset):
        return frozenset(_clone_payload(item) for item in value)
    if isinstance(value, deque):
        return deque(_clone_payload(item) for item in value)
    try:
        return deepcopy(value)
    except Exception:
        return value


@dataclass(frozen=True)
class SubscriptionHandle:
    """Opaque handle returned when subscribing to the bus."""

    event_type: Optional[str]
    callback: EventCallback
    priority: int
    sequence: int


@dataclass(frozen=True, slots=True)
class SequenceMatcher:
    """Matcher describing a single step in a sequence detector."""

    event_type: str
    predicate: Callable[[Input], bool] | None = None


@dataclass(frozen=True, slots=True)
class PlaylistStep:
    """Descriptor describing a scheduled event emitted by a playlist."""

    event_type: str
    data: Any = None
    offset: float = 0.0
    repeat: int = 1
    interval: float | None = None
    producer_id: int = 0

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise ValueError("PlaylistStep.offset must be non-negative")
        if self.repeat < 1:
            raise ValueError("PlaylistStep.repeat must be at least 1")
        if self.repeat > 1 and (self.interval is None or self.interval <= 0):
            raise ValueError(
                "PlaylistStep.interval must be positive when repeat > 1"
            )


@dataclass(frozen=True, slots=True)
class EventPlaylist:
    """Immutable playlist definition that can be triggered on the bus."""

    name: str
    steps: Sequence[PlaylistStep]
    trigger_event_type: str | None = None
    interrupt_events: Sequence[str] = ()
    completion_event_type: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.steps:
            raise ValueError("EventPlaylist requires at least one step")
        object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "interrupt_events", frozenset(self.interrupt_events))
        if self.metadata is not None:
            object.__setattr__(
                self, "metadata", MappingProxyType(dict(self.metadata))
            )


@dataclass(frozen=True, slots=True)
class PlaylistHandle:
    """Handle referencing a registered playlist definition."""

    playlist_id: str


@dataclass(frozen=True, slots=True)
class VirtualPeripheralHandle:
    """Handle referencing a registered virtual peripheral."""

    peripheral_id: str


@dataclass(frozen=True, slots=True)
class VirtualPeripheralDefinition:
    """Definition describing how to construct a virtual peripheral."""

    name: str
    event_types: Sequence[str]
    factory: Callable[["VirtualPeripheralContext"], "_VirtualPeripheral"]
    priority: int = 0
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.event_types:
            raise ValueError("VirtualPeripheralDefinition requires event_types")
        object.__setattr__(self, "event_types", tuple(self.event_types))
        if self.metadata is not None:
            object.__setattr__(
                self, "metadata", MappingProxyType(dict(self.metadata))
            )


class VirtualPeripheralContext:
    """Execution context shared with virtual peripherals."""

    def __init__(
        self,
        bus: "EventBus",
        definition: VirtualPeripheralDefinition,
        handle: VirtualPeripheralHandle,
    ) -> None:
        self._bus = bus
        self._definition = definition
        self._handle = handle

    @property
    def definition(self) -> VirtualPeripheralDefinition:
        return self._definition

    @property
    def state_store(self) -> StateStore:
        return self._bus.state_store

    def monotonic(self) -> float:
        return perf_counter()

    @property
    def playlists(self) -> "EventPlaylistManager":
        return self._bus.playlists

    def emit(self, event_type: str, data: Any, *, producer_id: int = 0) -> None:
        payload: Any
        if isinstance(data, dict):
            payload = dict(data)
        else:
            payload = {"value": data}

        if "virtual_peripheral" not in payload:
            descriptor: dict[str, Any] = {
                "id": self._handle.peripheral_id,
                "name": self._definition.name,
            }
            if self._definition.metadata is not None:
                descriptor["metadata"] = dict(self._definition.metadata)
            payload["virtual_peripheral"] = descriptor

        self._bus.emit(event_type, data=payload, producer_id=producer_id)

    @staticmethod
    def describe(event: Input) -> Mapping[str, Any]:
        return {
            "event_type": event.event_type,
            "producer_id": event.producer_id,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
        }


class _VirtualPeripheral(abc.ABC):
    """Base class for virtual peripherals managed by the bus."""

    def __init__(self, context: VirtualPeripheralContext) -> None:
        self._context = context

    @abc.abstractmethod
    def handle(self, event: Input) -> None:
        """Process ``event`` and emit any aggregated outputs."""

    def shutdown(self) -> None:
        """Hook invoked when the peripheral is unregistered."""


class _PlaylistRunner:
    """Internal helper that plays a playlist in a background thread."""

    def __init__(
        self,
        manager: "EventPlaylistManager",
        playlist_id: str,
        playlist: EventPlaylist,
        trigger_event: Input | None,
    ) -> None:
        self._manager = manager
        self.playlist_id = playlist_id
        self.playlist = playlist
        self.trigger_event = trigger_event
        self.run_id = uuid.uuid4().hex
        self._thread = threading.Thread(
            target=self._run,
            name=f"EventPlaylist-{playlist.name}-{self.run_id[:8]}",
            daemon=True,
        )
        self._stop_event = threading.Event()
        self._finished = threading.Event()
        self._stop_reason: str | None = None
        self._interrupt_event: Input | None = None

        ordered = sorted(
            enumerate(self.playlist.steps),
            key=lambda item: (item[1].offset, item[0]),
        )
        self._ordered_steps: Sequence[tuple[int, PlaylistStep]] = tuple(ordered)

    def start(self) -> None:
        self._thread.start()

    def stop(self, reason: str, interrupt_event: Input | None = None) -> None:
        if reason not in {"cancelled", "interrupted"}:
            raise ValueError("Unsupported stop reason")
        if self._finished.is_set():
            return
        if self._stop_reason is None:
            self._stop_reason = reason
            self._interrupt_event = interrupt_event
            self._stop_event.set()

    def join(self, timeout: float | None = None) -> bool:
        self._thread.join(timeout)
        return self._finished.is_set()

    def _wait_until(self, target_time: float) -> bool:
        remaining = max(0.0, target_time - perf_counter())
        if remaining <= 0:
            return not self._stop_event.is_set()
        return not self._stop_event.wait(remaining)

    def _run(self) -> None:
        start_time = perf_counter()
        for step_index, step in self._ordered_steps:
            scheduled_time = start_time + step.offset
            if not self._wait_until(scheduled_time):
                break

            occurrences = step.repeat
            for repeat_index in range(occurrences):
                if self._stop_event.is_set():
                    break
                if repeat_index and step.interval is not None:
                    scheduled_time += step.interval
                    if not self._wait_until(scheduled_time):
                        break

                if self._stop_event.is_set():
                    break

                elapsed = scheduled_time - start_time
                self._manager._dispatch_step(
                    self,
                    step,
                    step_index,
                    repeat_index,
                    max(0.0, elapsed),
                )

            if self._stop_event.is_set():
                break

        if self._stop_reason is None and self._stop_event.is_set():
            self._stop_reason = "cancelled"

        reason = self._stop_reason or "completed"
        self._manager._finalize_run(self, reason, self._interrupt_event)
        self._finished.set()


class EventPlaylistManager:
    """Coordinator for event playlists executed on the bus."""

    EVENT_CREATED = "event.playlist.created"
    EVENT_EMITTED = "event.playlist.emitted"
    EVENT_STOPPED = "event.playlist.stopped"

    def __init__(self, bus: "EventBus") -> None:
        self._bus = bus
        self._lock = threading.RLock()
        self._playlists: MutableMapping[str, EventPlaylist] = {}
        self._triggers: MutableMapping[str, SubscriptionHandle] = {}
        self._interrupt_subscribers: MutableMapping[str, SubscriptionHandle] = {}
        self._runs_by_interrupt: MutableMapping[str, set[str]] = defaultdict(set)
        self._active_runs: MutableMapping[str, _PlaylistRunner] = {}

    def register(self, playlist: EventPlaylist) -> PlaylistHandle:
        """Register ``playlist`` and return a handle."""

        playlist_id = uuid.uuid4().hex
        handle = PlaylistHandle(playlist_id)

        with self._lock:
            self._playlists[playlist_id] = playlist

        if playlist.trigger_event_type is not None:
            trigger_handle = self._bus.subscribe(
                playlist.trigger_event_type,
                lambda event, pid=playlist_id: self.start(pid, trigger_event=event),
                priority=100,
            )
            with self._lock:
                self._triggers[playlist_id] = trigger_handle

        return handle

    def update(self, handle: PlaylistHandle, playlist: EventPlaylist) -> None:
        """Replace the definition referenced by ``handle`` with ``playlist``."""

        trigger_handle: SubscriptionHandle | None = None
        with self._lock:
            if handle.playlist_id not in self._playlists:
                raise KeyError(f"Unknown playlist id: {handle.playlist_id}")
            previous_trigger = self._triggers.pop(handle.playlist_id, None)

        if previous_trigger is not None:
            self._bus.unsubscribe(previous_trigger)

        if playlist.trigger_event_type is not None:
            trigger_handle = self._bus.subscribe(
                playlist.trigger_event_type,
                lambda event, pid=handle.playlist_id: self.start(
                    pid, trigger_event=event
                ),
                priority=100,
            )

        with self._lock:
            self._playlists[handle.playlist_id] = playlist
            if trigger_handle is not None:
                self._triggers[handle.playlist_id] = trigger_handle

    def remove(self, handle: PlaylistHandle) -> None:
        """Unregister the playlist referenced by ``handle``."""

        trigger_handle: SubscriptionHandle | None = None
        with self._lock:
            self._playlists.pop(handle.playlist_id, None)
            trigger_handle = self._triggers.pop(handle.playlist_id, None)

        if trigger_handle is not None:
            self._bus.unsubscribe(trigger_handle)

    def list_definitions(self) -> Mapping[str, EventPlaylist]:
        """Return a read-only mapping of registered playlist definitions."""

        with self._lock:
            return MappingProxyType(dict(self._playlists))

    def start(
        self,
        handle: PlaylistHandle | str,
        *,
        trigger_event: Input | None = None,
    ) -> str:
        """Start executing the playlist referenced by ``handle``."""

        playlist_id = handle if isinstance(handle, str) else handle.playlist_id
        with self._lock:
            playlist = self._playlists.get(playlist_id)
            if playlist is None:
                raise KeyError(f"Unknown playlist id: {playlist_id}")

        runner = _PlaylistRunner(self, playlist_id, playlist, trigger_event)

        with self._lock:
            self._active_runs[runner.run_id] = runner
            for event_type in playlist.interrupt_events:
                runs = self._runs_by_interrupt[event_type]
                runs.add(runner.run_id)
                if event_type not in self._interrupt_subscribers:
                    self._interrupt_subscribers[event_type] = self._bus.subscribe(
                        event_type,
                        lambda event, et=event_type: self._handle_interrupt(et, event),
                        priority=100,
                    )

            payload = self._build_created_payload(runner)

        self._bus.emit(self.EVENT_CREATED, data=payload)
        runner.start()
        return runner.run_id

    def stop(self, run_id: str, *, reason: str = "cancelled") -> None:
        with self._lock:
            runner = self._active_runs.get(run_id)
        if runner is None:
            return
        runner.stop(reason)

    def join(self, run_id: str, timeout: float | None = None) -> bool:
        with self._lock:
            runner = self._active_runs.get(run_id)
        if runner is None:
            return True
        return runner.join(timeout)

    def _handle_interrupt(self, event_type: str, event: Input) -> None:
        with self._lock:
            run_ids = tuple(self._runs_by_interrupt.get(event_type, ()))

        for run_id in run_ids:
            with self._lock:
                runner = self._active_runs.get(run_id)
            if runner is None:
                continue
            runner.stop("interrupted", interrupt_event=event)

    def _dispatch_step(
        self,
        runner: _PlaylistRunner,
        step: PlaylistStep,
        step_index: int,
        repeat_index: int,
        scheduled_offset: float,
    ) -> None:
        event_data = _clone_payload(step.data)
        telemetry_data = _clone_payload(event_data)
        event = Input(
            event_type=step.event_type,
            data=event_data,
            producer_id=step.producer_id,
        )
        self._bus.emit(event)

        payload = {
            "playlist_id": runner.run_id,
            "definition_id": runner.playlist_id,
            "playlist_name": runner.playlist.name,
            "step_index": step_index,
            "repeat_index": repeat_index,
            "event_type": step.event_type,
            "producer_id": step.producer_id,
            "offset": scheduled_offset,
            "data": telemetry_data,
        }
        if runner.playlist.metadata is not None:
            payload["playlist_metadata"] = _clone_payload(
                runner.playlist.metadata
            )
        if runner.trigger_event is not None:
            payload["trigger_event"] = {
                "event_type": runner.trigger_event.event_type,
                "producer_id": runner.trigger_event.producer_id,
                "data": _clone_payload(runner.trigger_event.data),
            }
        self._bus.emit(self.EVENT_EMITTED, data=payload)

    def _finalize_run(
        self,
        runner: _PlaylistRunner,
        reason: str,
        interrupt_event: Input | None,
    ) -> None:
        with self._lock:
            if runner.run_id not in self._active_runs:
                return
            self._active_runs.pop(runner.run_id, None)
            for event_type in runner.playlist.interrupt_events:
                runs = self._runs_by_interrupt.get(event_type)
                if runs is None:
                    continue
                runs.discard(runner.run_id)
                if not runs:
                    self._runs_by_interrupt.pop(event_type, None)
                    handle = self._interrupt_subscribers.pop(event_type, None)
                    if handle is not None:
                        self._bus.unsubscribe(handle)

        payload = {
            "playlist_id": runner.run_id,
            "definition_id": runner.playlist_id,
            "playlist_name": runner.playlist.name,
            "reason": reason,
        }
        if runner.playlist.metadata is not None:
            payload["playlist_metadata"] = _clone_payload(
                runner.playlist.metadata
            )
        if interrupt_event is not None:
            payload["interrupt_event"] = {
                "event_type": interrupt_event.event_type,
                "producer_id": interrupt_event.producer_id,
                "data": _clone_payload(interrupt_event.data),
            }
        self._bus.emit(self.EVENT_STOPPED, data=payload)

        if reason == "completed" and runner.playlist.completion_event_type:
            completion_payload = {
                "playlist_id": runner.run_id,
                "definition_id": runner.playlist_id,
                "playlist_name": runner.playlist.name,
            }
            if runner.playlist.metadata is not None:
                completion_payload["playlist_metadata"] = _clone_payload(
                    runner.playlist.metadata
                )
            if runner.trigger_event is not None:
                completion_payload["trigger_event"] = {
                    "event_type": runner.trigger_event.event_type,
                    "producer_id": runner.trigger_event.producer_id,
                    "data": _clone_payload(runner.trigger_event.data),
                }
            self._bus.emit(
                runner.playlist.completion_event_type,
                data=completion_payload,
            )

    def _build_created_payload(self, runner: _PlaylistRunner) -> Mapping[str, Any]:
        payload: dict[str, Any] = {
            "playlist_id": runner.run_id,
            "definition_id": runner.playlist_id,
            "playlist_name": runner.playlist.name,
            "steps": [
                {
                    "event_type": step.event_type,
                    "offset": step.offset,
                    "repeat": step.repeat,
                    "interval": step.interval,
                    "producer_id": step.producer_id,
                    "data": _clone_payload(step.data),
                }
                for step in runner.playlist.steps
            ],
        }
        if runner.playlist.metadata is not None:
            payload["playlist_metadata"] = _clone_payload(
                runner.playlist.metadata
            )
        if runner.trigger_event is not None:
            payload["trigger_event"] = {
                "event_type": runner.trigger_event.event_type,
                "producer_id": runner.trigger_event.producer_id,
                "data": _clone_payload(runner.trigger_event.data),
            }
        return payload


class VirtualPeripheralManager:
    """Coordinator for virtual peripherals attached to the bus."""

    def __init__(self, bus: "EventBus") -> None:
        self._bus = bus
        self._lock = threading.RLock()
        self._definitions: MutableMapping[str, VirtualPeripheralDefinition] = {}
        self._instances: MutableMapping[str, _VirtualPeripheral] = {}
        self._subscriptions: MutableMapping[str, List[SubscriptionHandle]] = {}

    def register(self, definition: VirtualPeripheralDefinition) -> VirtualPeripheralHandle:
        handle = VirtualPeripheralHandle(uuid.uuid4().hex)
        self._bind(handle, definition)
        return handle

    def update(
        self,
        handle: VirtualPeripheralHandle,
        definition: VirtualPeripheralDefinition,
    ) -> None:
        with self._lock:
            if handle.peripheral_id not in self._definitions:
                raise KeyError(f"Unknown virtual peripheral id: {handle.peripheral_id}")
        self._unbind(handle)
        self._bind(handle, definition)

    def remove(self, handle: VirtualPeripheralHandle) -> None:
        self._unbind(handle)

    def list_definitions(self) -> Mapping[str, VirtualPeripheralDefinition]:
        with self._lock:
            return MappingProxyType(dict(self._definitions))

    def _bind(
        self,
        handle: VirtualPeripheralHandle,
        definition: VirtualPeripheralDefinition,
    ) -> None:
        context = VirtualPeripheralContext(self._bus, definition, handle)
        instance = definition.factory(context)
        subscriptions: List[SubscriptionHandle] = []

        for event_type in definition.event_types:
            subscription = self._bus.subscribe(
                event_type,
                lambda event, pid=handle.peripheral_id: self._route_event(pid, event),
                priority=definition.priority,
            )
            subscriptions.append(subscription)

        with self._lock:
            self._definitions[handle.peripheral_id] = definition
            self._instances[handle.peripheral_id] = instance
            self._subscriptions[handle.peripheral_id] = subscriptions

    def _unbind(self, handle: VirtualPeripheralHandle) -> None:
        with self._lock:
            definition = self._definitions.pop(handle.peripheral_id, None)
            instance = self._instances.pop(handle.peripheral_id, None)
            subscriptions = self._subscriptions.pop(handle.peripheral_id, None)

        if subscriptions:
            for subscription in subscriptions:
                self._bus.unsubscribe(subscription)

        if instance is not None:
            try:
                instance.shutdown()
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception(
                    "Virtual peripheral %s shutdown failed", handle.peripheral_id
                )

        if definition is not None:
            _LOGGER.debug(
                "Unregistered virtual peripheral %s", definition.name
            )

    def _route_event(self, peripheral_id: str, event: Input) -> None:
        with self._lock:
            instance = self._instances.get(peripheral_id)
            definition = self._definitions.get(peripheral_id)

        if instance is None:
            return

        try:
            instance.handle(event)
        except Exception:
            name = definition.name if definition is not None else peripheral_id
            _LOGGER.exception(
                "Virtual peripheral %s failed for event %s", name, event
            )


class _GatedMirrorVirtualPeripheral(_VirtualPeripheral):
    """Mirror events from another producer when a gate is enabled."""

    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        gate_event_types: Sequence[str],
        mirror_event_types: Sequence[str],
        output_producer_id: int,
        predicate: GatePredicate,
        initial_state: bool,
    ) -> None:
        super().__init__(context)
        if not mirror_event_types:
            raise ValueError("mirror_event_types must not be empty")
        if not gate_event_types:
            raise ValueError("gate_event_type must not be empty")
        self._gate_event_types = frozenset(gate_event_types)
        self._mirror_event_types = frozenset(mirror_event_types)
        self._output_producer_id = output_producer_id
        self._predicate = predicate
        self._enabled = initial_state

    def handle(self, event: Input) -> None:
        if event.event_type in self._gate_event_types:
            try:
                self._enabled = bool(self._predicate(self._context, event))
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception(
                    "Virtual peripheral %s failed to evaluate gate event",
                    self._context.definition.name,
                )
            return

        if event.event_type in self._mirror_event_types and self._enabled:
            payload = _clone_payload(event.data)
            self._context.emit(
                event.event_type,
                payload,
                producer_id=self._output_producer_id,
            )


class _DoubleTapVirtualPeripheral(_VirtualPeripheral):
    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        window: float,
        output_event_type: str,
    ) -> None:
        super().__init__(context)
        if window <= 0:
            raise ValueError("window must be positive")
        self._window = window
        self._output_event_type = output_event_type
        self._last_event: MutableMapping[int, tuple[float, Input]] = {}

    def handle(self, event: Input) -> None:
        now = self._context.monotonic()
        previous = self._last_event.get(event.producer_id)

        if previous is not None:
            last_time, last_event = previous
            if now - last_time <= self._window:
                payload = {
                    "events": [
                        VirtualPeripheralContext.describe(last_event),
                        VirtualPeripheralContext.describe(event),
                    ]
                }
                self._context.emit(
                    self._output_event_type,
                    payload,
                    producer_id=event.producer_id,
                )
                self._last_event.pop(event.producer_id, None)
                return

        self._last_event[event.producer_id] = (now, event)

    def shutdown(self) -> None:
        self._last_event.clear()


class _SimultaneousVirtualPeripheral(_VirtualPeripheral):
    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        window: float,
        required_sources: int,
        output_event_type: str,
    ) -> None:
        super().__init__(context)
        if window <= 0:
            raise ValueError("window must be positive")
        if required_sources < 2:
            raise ValueError("required_sources must be at least 2")
        self._window = window
        self._required_sources = required_sources
        self._output_event_type = output_event_type
        self._pending: MutableMapping[str, Deque[tuple[float, Input]]] = defaultdict(deque)

    def handle(self, event: Input) -> None:
        bucket = self._pending[event.event_type]
        now = self._context.monotonic()

        while bucket and now - bucket[0][0] > self._window:
            bucket.popleft()

        bucket.append((now, event))

        unique: dict[int, Input] = {}
        for _, pending_event in reversed(bucket):
            if pending_event.producer_id not in unique:
                unique[pending_event.producer_id] = pending_event

        if len(unique) >= self._required_sources:
            ordered = list(reversed(list(unique.values())))
            payload = {
                "events": [
                    VirtualPeripheralContext.describe(candidate)
                    for candidate in ordered
                ]
            }
            self._context.emit(
                self._output_event_type,
                payload,
                producer_id=0,
            )
            bucket.clear()

    def shutdown(self) -> None:
        self._pending.clear()


class _SequenceVirtualPeripheral(_VirtualPeripheral):
    def __init__(
        self,
        context: VirtualPeripheralContext,
        matchers: Sequence[SequenceMatcher],
        *,
        timeout: float | None,
        output_event_type: str,
    ) -> None:
        super().__init__(context)
        if not matchers:
            raise ValueError("matchers cannot be empty")
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive when provided")
        self._matchers = tuple(matchers)
        self._timeout = timeout
        self._output_event_type = output_event_type
        self._progress: MutableMapping[int, tuple[int, float, List[Input]]] = {}

    def handle(self, event: Input) -> None:
        now = self._context.monotonic()
        state = self._progress.get(event.producer_id)
        index = 0
        history: List[Input] = []

        if state is not None:
            index, last_time, history = state
            if self._timeout is not None and now - last_time > self._timeout:
                index = 0
                history = []

        if self._matches(index, event):
            new_history = history + [event]
            next_index = index + 1
            if next_index == len(self._matchers):
                payload = {
                    "sequence": [
                        VirtualPeripheralContext.describe(item)
                        for item in new_history
                    ]
                }
                self._context.emit(
                    self._output_event_type,
                    payload,
                    producer_id=event.producer_id,
                )
                self._progress.pop(event.producer_id, None)
            else:
                self._progress[event.producer_id] = (next_index, now, new_history)
            return

        if self._matches(0, event):
            self._progress[event.producer_id] = (1, now, [event])
        else:
            self._progress.pop(event.producer_id, None)

    def shutdown(self) -> None:
        self._progress.clear()

    def _matches(self, index: int, event: Input) -> bool:
        if index >= len(self._matchers):
            return False
        matcher = self._matchers[index]
        if event.event_type != matcher.event_type:
            return False
        if matcher.predicate is not None:
            return matcher.predicate(event)
        return True


class _PlaylistTriggerVirtualPeripheral(_VirtualPeripheral):
    """Start a playlist when gate events satisfy an optional predicate."""

    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        gate_event_types: Sequence[str],
        playlist: EventPlaylist,
        predicate: GatePredicate | None,
        cancel_active_runs: bool,
    ) -> None:
        super().__init__(context)
        if not gate_event_types:
            raise ValueError("gate_event_types must not be empty")
        if playlist.trigger_event_type is not None:
            raise ValueError(
                "playlist.trigger_event_type must be None for gated playlists"
            )
        self._gate_event_types = frozenset(gate_event_types)
        self._predicate = predicate
        self._cancel_active_runs = cancel_active_runs
        self._playlist_handle = context.playlists.register(playlist)
        self._active_runs: set[str] = set()

    def handle(self, event: Input) -> None:
        if event.event_type == EventPlaylistManager.EVENT_STOPPED:
            data = event.data if isinstance(event.data, MappingABC) else {}
            definition_id = data.get("definition_id") if data else None
            if definition_id == self._playlist_handle.playlist_id:
                run_id = data.get("playlist_id") if data else None
                if run_id:
                    self._active_runs.discard(run_id)
            return

        if event.event_type not in self._gate_event_types:
            return

        should_trigger = True
        if self._predicate is not None:
            try:
                should_trigger = bool(self._predicate(self._context, event))
            except Exception:  # pragma: no cover - defensive logging
                _LOGGER.exception(
                    "Virtual peripheral %s failed to evaluate gate predicate",
                    self._context.definition.name,
                )
                return

        if not should_trigger:
            return

        if self._cancel_active_runs and self._active_runs:
            for run_id in tuple(self._active_runs):
                self._context.playlists.stop(run_id, reason="cancelled")

        try:
            run_id = self._context.playlists.start(
                self._playlist_handle, trigger_event=event
            )
        except Exception:  # pragma: no cover - defensive logging
            _LOGGER.exception(
                "Virtual peripheral %s failed to start playlist",
                self._context.definition.name,
            )
            return

        self._active_runs.add(run_id)

    def shutdown(self) -> None:
        for run_id in tuple(self._active_runs):
            self._context.playlists.stop(run_id, reason="cancelled")
        self._active_runs.clear()
        self._context.playlists.remove(self._playlist_handle)


def double_tap_virtual_peripheral(
    source_event_type: str,
    *,
    output_event_type: str,
    window: float = 0.3,
    name: str | None = None,
    priority: int = 50,
    metadata: Mapping[str, Any] | None = None,
) -> VirtualPeripheralDefinition:
    resolved_name = name or f"{source_event_type}.double_tap"

    def factory(context: VirtualPeripheralContext) -> _VirtualPeripheral:
        return _DoubleTapVirtualPeripheral(
            context,
            window=window,
            output_event_type=output_event_type,
        )

    return VirtualPeripheralDefinition(
        name=resolved_name,
        event_types=(source_event_type,),
        factory=factory,
        priority=priority,
        metadata=metadata,
    )


def simultaneous_virtual_peripheral(
    event_type: str,
    *,
    output_event_type: str,
    window: float = 0.01,
    required_sources: int = 2,
    name: str | None = None,
    priority: int = 50,
    metadata: Mapping[str, Any] | None = None,
) -> VirtualPeripheralDefinition:
    resolved_name = name or f"{event_type}.simultaneous"

    def factory(context: VirtualPeripheralContext) -> _VirtualPeripheral:
        return _SimultaneousVirtualPeripheral(
            context,
            window=window,
            required_sources=required_sources,
            output_event_type=output_event_type,
        )

    return VirtualPeripheralDefinition(
        name=resolved_name,
        event_types=(event_type,),
        factory=factory,
        priority=priority,
        metadata=metadata,
    )


def sequence_virtual_peripheral(
    name: str,
    matchers: Sequence[SequenceMatcher],
    *,
    output_event_type: str,
    timeout: float | None = 1.0,
    priority: int = 50,
    metadata: Mapping[str, Any] | None = None,
) -> VirtualPeripheralDefinition:
    if not matchers:
        raise ValueError("matchers must not be empty")
    event_types = tuple({matcher.event_type for matcher in matchers})

    def factory(context: VirtualPeripheralContext) -> _VirtualPeripheral:
        return _SequenceVirtualPeripheral(
            context,
            matchers,
            timeout=timeout,
            output_event_type=output_event_type,
        )

    return VirtualPeripheralDefinition(
        name=name,
        event_types=event_types,
        factory=factory,
        priority=priority,
        metadata=metadata,
    )


def _default_gate_predicate(
    context: "VirtualPeripheralContext", event: Input
) -> bool:
    data = event.data
    if isinstance(data, Mapping):
        for key in ("pressed", "state", "enabled", "value"):
            if key in data:
                return bool(data[key])
        return bool(data)
    return bool(data)


def gated_mirror_virtual_peripheral(
    name: str,
    *,
    gate_event_type: str | Sequence[str],
    mirror_event_types: str | Sequence[str],
    output_producer_id: int,
    priority: int = 0,
    metadata: Mapping[str, Any] | None = None,
    gate_predicate: GatePredicate | None = None,
    initial_state: bool = False,
) -> VirtualPeripheralDefinition:
    """Return a definition for a gate-controlled mirroring peripheral.

    Parameters
    ----------
    gate_event_type:
        Event type or types that toggle the gate. Each matching event is passed
        to ``gate_predicate`` to determine whether mirroring should be enabled.
    gate_predicate:
        Callable receiving the :class:`VirtualPeripheralContext` and the gate
        :class:`Input`. Returning ``True`` enables mirroring, while ``False``
        disables it.
    """

    if isinstance(gate_event_type, str):
        gate_types: tuple[str, ...] = (gate_event_type,)
    else:
        gate_types = tuple(gate_event_type)
    if not gate_types:
        raise ValueError("gate_event_type must not be empty")
    if isinstance(mirror_event_types, str):
        mirror_types: tuple[str, ...] = (mirror_event_types,)
    else:
        mirror_types = tuple(mirror_event_types)
    if not mirror_types:
        raise ValueError("mirror_event_types must not be empty")

    if gate_predicate is None:
        gate_predicate = _default_gate_predicate

    event_types: list[str] = []
    for candidate in (*gate_types, *mirror_types):
        if candidate not in event_types:
            event_types.append(candidate)

    def factory(context: VirtualPeripheralContext) -> _VirtualPeripheral:
        return _GatedMirrorVirtualPeripheral(
            context,
            gate_event_types=gate_types,
            mirror_event_types=mirror_types,
            output_producer_id=output_producer_id,
            predicate=gate_predicate,
            initial_state=initial_state,
        )

    return VirtualPeripheralDefinition(
        name=name,
        event_types=tuple(event_types),
        factory=factory,
        priority=priority,
        metadata=metadata,
    )


def gated_playlist_virtual_peripheral(
    gate_event_types: Sequence[str],
    *,
    playlist: EventPlaylist,
    predicate: GatePredicate | None = None,
    cancel_active_runs: bool = False,
    name: str | None = None,
    priority: int = 50,
    metadata: Mapping[str, Any] | None = None,
) -> VirtualPeripheralDefinition:
    """Return a virtual peripheral that starts ``playlist`` when gated events fire."""

    if not gate_event_types:
        raise ValueError("gate_event_types must not be empty")

    resolved_name = name or f"{playlist.name}.gated"
    event_types = tuple(
        dict.fromkeys(
            (*gate_event_types, EventPlaylistManager.EVENT_STOPPED)
        )
    )

    def factory(context: VirtualPeripheralContext) -> _VirtualPeripheral:
        return _PlaylistTriggerVirtualPeripheral(
            context,
            gate_event_types=gate_event_types,
            playlist=playlist,
            predicate=predicate,
            cancel_active_runs=cancel_active_runs,
        )

    return VirtualPeripheralDefinition(
        name=resolved_name,
        event_types=event_types,
        factory=factory,
        priority=priority,
        metadata=metadata,
    )


class EventBus:
    """Synchronous pub/sub dispatcher for :class:`Input` events."""

    def __init__(self, *, state_store: StateStore | None = None) -> None:
        self._subscribers: MutableMapping[Optional[str], List[SubscriptionHandle]] = defaultdict(list)
        self._next_sequence = 0
        self._state_store = state_store or StateStore()
        self._playlist_manager = EventPlaylistManager(self)
        self._virtual_peripherals = VirtualPeripheralManager(self)

    # Public API ---------------------------------------------------------
    def subscribe(
        self,
        event_type: Optional[str],
        callback: EventCallback,
        *,
        priority: int = 0,
    ) -> SubscriptionHandle:
        """Register ``callback`` for ``event_type`` events."""

        handle = SubscriptionHandle(event_type, callback, priority, self._next_sequence)
        self._next_sequence += 1
        bucket = self._subscribers[event_type]
        bucket.append(handle)
        bucket.sort(key=lambda item: (-item.priority, item.sequence))
        return handle

    def unsubscribe(self, handle: SubscriptionHandle) -> None:
        """Remove ``handle`` from the bus if it is still registered."""

        bucket = self._subscribers.get(handle.event_type)
        if not bucket:
            return
        try:
            bucket.remove(handle)
        except ValueError:
            return
        if not bucket:
            self._subscribers.pop(handle.event_type, None)

    def emit(self, event: Input | str, /, data=None, *, producer_id: int = 0) -> None:
        """Emit an :class:`Input` instance to subscribed callbacks."""

        if isinstance(event, Input):
            input_event = event
        else:
            input_event = Input(event_type=event, data=data, producer_id=producer_id)
        self._state_store.update(input_event)
        started_at = perf_counter()
        dispatched = 0
        for handle in self._iter_targets(input_event.event_type):
            try:
                handle.callback(input_event)
                dispatched += 1
            except Exception:
                _LOGGER.exception(
                    "EventBus subscriber %s failed for event %s", handle.callback, input_event
                )
        duration = perf_counter() - started_at
        _LOGGER.debug(
            "Dispatched event %s from producer %s to %d subscriber(s) in %.3fms",
            input_event.event_type,
            input_event.producer_id,
            dispatched,
            duration * 1000,
        )

    def run_on_event(
        self, event_type: Optional[str], *, priority: int = 0
    ) -> Callable[[EventCallback], EventCallback]:
        """Decorator variant of :meth:`subscribe`."""

        def decorator(callback: EventCallback) -> EventCallback:
            self.subscribe(event_type, callback, priority=priority)
            return callback

        return decorator

    @property
    def state_store(self) -> StateStore:
        """Return the state store maintained by the bus."""

        return self._state_store

    @property
    def playlists(self) -> EventPlaylistManager:
        """Return the playlist manager bound to this bus."""

        return self._playlist_manager

    @property
    def virtual_peripherals(self) -> VirtualPeripheralManager:
        """Return the virtual peripheral manager bound to this bus."""

        return self._virtual_peripherals

    # Internal helpers ---------------------------------------------------
    def _iter_targets(self, event_type: str) -> Iterable[SubscriptionHandle]:
        """Yield subscribers in priority order, including wildcards."""

        handles: List[SubscriptionHandle] = []
        wildcard = self._subscribers.get(None)
        if wildcard:
            handles.extend(wildcard)
        specific = self._subscribers.get(event_type)
        if specific:
            handles.extend(specific)
        for handle in sorted(handles, key=lambda item: (-item.priority, item.sequence)):
            yield handle

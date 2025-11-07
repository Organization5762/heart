# Event Playlist Scheduler

## Problem Statement

Document the new event playlist feature and virtual peripheral aggregators so developers understand how timed sequences and composite gestures of `Input` events can be orchestrated through the core event bus.

## Materials

- `src/heart/peripheral/core/event_bus.py`
- `tests/peripheral/test_event_bus.py`

## Playlist Abstractions

`EventPlaylist` encapsulates a named sequence of `PlaylistStep` descriptors. Each step declares the target event type, payload, producer, an absolute offset, and optional repetition with a fixed interval. The constructor normalises the immutable shape by coercing the step list to a tuple, the interrupt list to a `frozenset`, and metadata to a `MappingProxyType` for thread-safe read access. Offsets must be non-negative and repeating steps must provide a positive interval to guard against runaway schedulers.【F:src/heart/peripheral/core/event_bus.py†L24-L88】

`PlaylistHandle` is an opaque identifier returned when a definition is registered. Handles remain stable even if the playlist is updated because the manager replaces trigger subscriptions in place. Consumers can store handles in configuration modules or runtime registries without leaking implementation details.【F:src/heart/peripheral/core/event_bus.py†L90-L148】【F:src/heart/peripheral/core/event_bus.py†L150-L197】

## Execution Lifecycle

`EventPlaylistManager` owns registration, trigger wiring, execution, and teardown. The manager hangs off `EventBus.playlists`, allowing existing systems to drive sequences through the shared bus rather than ad-hoc timers. Registration stores the definition before subscribing to its trigger to avoid races where a start event lands before the playlist exists. Updating a playlist reuses the original identifier, unsubscribes the old trigger, and rebinds the new trigger lambda that delegates to `start()`.【F:src/heart/peripheral/core/event_bus.py†L197-L269】

Starting a playlist instantiates an internal `_PlaylistRunner` with a unique run identifier, caches it, and optionally wires interrupt subscriptions. Runners sort steps by offset and execute them on a dedicated daemon thread that honours stop events by checking a shared `threading.Event`. Each emission calls back into the manager so the bus can emit the real `Input`, record telemetry, and publish playlist control events. Once all scheduled steps finish (or a stop request fires), the runner notifies the manager to emit `event.playlist.stopped`, clean up interrupt subscriptions, and optionally send a caller-specified completion event that higher-level modes can observe.【F:src/heart/peripheral/core/event_bus.py†L100-L194】【F:src/heart/peripheral/core/event_bus.py†L269-L374】

## Interrupt Handling

Interrupt events are tracked per run. When a definition declares `interrupt_events`, the manager shares a high-priority subscription for each unique event type. The callback inspects the active runs mapped to that event and signals `runner.stop("interrupted")`. The runner then drops out of its scheduling loop, leading `_finalize_run()` to broadcast a stopped payload that includes the interrupt event metadata so downstream systems can correlate the stoppage.【F:src/heart/peripheral/core/event_bus.py†L297-L333】【F:src/heart/peripheral/core/event_bus.py†L333-L351】

Manual cancellation is exposed through `EventPlaylistManager.stop(run_id)`, while `join()` lets synchronous code wait for completion—useful in tests. Active runs also maintain metadata and trigger context so instrumentation is consistent whether a playlist was started via an upstream event or direct call. Tests assert that manual runs emit three colour updates, publish playlist telemetry, and flag completion metadata, while triggered runs respond to a stop event and expose the triggering payload.【F:src/heart/peripheral/core/event_bus.py†L269-L374】【F:tests/peripheral/test_event_bus.py†L53-L144】

## Observability

Every playlist publishes three core lifecycle events:

- `event.playlist.created` with the playlist metadata, trigger context, and normalised steps.
- `event.playlist.emitted` after each dispatched `Input`, including the scheduled offset, repeat index, and event payload.
- `event.playlist.stopped` upon completion, cancellation, or interruption, with the reason and optional interrupt payload.

If a definition supplies `completion_event_type`, the manager emits that custom event when the run finishes successfully. These signals are stored in the shared `StateStore`, enabling downstream renderers or analytics tasks to observe playlists without bespoke plumbing.【F:src/heart/peripheral/core/event_bus.py†L314-L374】

## Virtual Peripheral Manager

Virtual peripherals extend the bus with aggregated gestures. `VirtualPeripheralDefinition` and `VirtualPeripheralHandle` mirror the playlist abstractions, storing immutable metadata and the factory used to construct a detector. Each definition registers to one or more event types and spawns a concrete `_VirtualPeripheral` instance with a `VirtualPeripheralContext`, giving detectors access to the bus, state store, a monotonic clock, and a helper that emits enriched events tagged with the originating virtual peripheral descriptor.【F:src/heart/peripheral/core/event_bus.py†L40-L143】【F:src/heart/peripheral/core/event_bus.py†L551-L653】

`VirtualPeripheralManager` owns registration, updates, and teardown. During `_bind()` it subscribes to each source event type at the requested priority, routing inputs through `_route_event()` so detectors can synchronously process them. `remove()` unsubscribes and calls `shutdown()` on the detector, ensuring gesture-specific caches (for example, pending taps) are cleared. The bus exposes the manager through `EventBus.virtual_peripherals`, letting applications register detectors alongside playlists without wiring their own subscription scaffolding.【F:src/heart/peripheral/core/event_bus.py†L541-L650】【F:src/heart/peripheral/core/event_bus.py†L698-L712】

## Gesture Aggregators

Three reference detectors demonstrate how to compose higher-level gestures:

- `_DoubleTapVirtualPeripheral` tracks the last press per producer and emits when the next press lands within the configured window, returning a payload that lists both raw inputs and the virtual peripheral metadata.【F:src/heart/peripheral/core/event_bus.py†L655-L690】
- `_SimultaneousVirtualPeripheral` keeps a sliding deque of inputs per event type, collapsing them by producer and emitting once enough distinct sources fire within the window; afterwards it clears the bucket to avoid duplicate notifications.【F:src/heart/peripheral/core/event_bus.py†L692-L732】
- `_SequenceVirtualPeripheral` steps through a series of `SequenceMatcher` predicates, maintaining per-producer progress and optional timeouts before emitting the completed sequence payload.【F:src/heart/peripheral/core/event_bus.py†L734-L779】

Factory helpers—`double_tap_virtual_peripheral`, `simultaneous_virtual_peripheral`, and `sequence_virtual_peripheral`—package the detectors into reusable definitions. They expose parameters for window durations, output event types, names, and metadata so configuration modules can register gestures declaratively.【F:src/heart/peripheral/core/event_bus.py†L781-L831】

The tests capture expected behaviour: the double-tap detector emits metadata-enriched payloads, the simultaneous detector requires distinct producers inside the 50 ms window, and the sequence detector recognises the Konami code. These assertions ensure the helper factories and manager integration behave as intended.【F:tests/peripheral/test_event_bus.py†L146-L213】

## Future Work

- Add persistence hooks so playlists can be described in configuration files and loaded at runtime.
- Extend `_PlaylistRunner` to support dynamic tempo changes by listening to control events that adjust offsets mid-run.
- Provide tooling for introspecting `list_definitions()` and visualising active runs in the debugging UI.
- Surface built-in gesture definitions through configuration schemas so applications can declare complex inputs without bespoke factories.

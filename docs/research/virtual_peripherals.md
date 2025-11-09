# Virtual Peripheral Aggregation Notes

## Problem Statement

Explain how virtual peripherals convert raw `Input` events into higher-level gestures on the event bus so teams can author new detectors and plan incremental rollouts.

## Materials

- `src/heart/peripheral/core/event_bus.py` virtual peripheral context, manager, and helper factories.
- Runtime logs that show event emissions during composite gesture detection.
- Representative input streams (switches, sensors, playlists) to validate aggregation timing.

## Architecture Overview

Virtual peripherals sit on top of the synchronous event bus. Each definition records the event types it listens for, the factory used to construct a detector, and optional metadata surfaced with every emitted payload ([descriptor schema](src/heart/peripheral/core/event_bus.py#L187-L213), [manager registration flow](src/heart/peripheral/core/event_bus.py#L590-L643)). When a definition is registered, the manager creates a `VirtualPeripheralContext`, instantiates the detector, and subscribes routing hooks for every source event type. The context exposes the shared state store, a monotonic clock for timing windows, and an `emit()` helper that automatically tags outgoing events with the originating virtual peripheral descriptor ([context helpers](src/heart/peripheral/core/event_bus.py#L163-L206)).

`VirtualPeripheralManager` tracks definitions, live instances, and their subscription handles under a re-entrant lock so updates and removals can safely tear down detectors. On removal it unsubscribes the hooks, calls `shutdown()` on the detector, and logs the teardown, ensuring stale detectors cannot continue emitting after reconfiguration ([manager teardown logic](src/heart/peripheral/core/event_bus.py#L590-L667)). Runtime delivery leverages the bus' standard subscription ordering, so priority controls provided on the definition influence when detectors run relative to other subscribers ([priority handling](src/heart/peripheral/core/event_bus.py#L632-L637)).

## Event Lifecycle

1. Register a `VirtualPeripheralDefinition` via the manager. Registration allocates a handle, constructs a detector, and binds bus subscriptions for all listed event types ([registration steps](src/heart/peripheral/core/event_bus.py#L600-L643)).
1. As matching inputs arrive, the bus invokes the manager's routing callback, which forwards the event to the detector instance associated with the handle ([routing callback](src/heart/peripheral/core/event_bus.py#L632-L682)).
1. Detectors evaluate their windows or predicates and call `context.emit()` to publish aggregated events. The helper copies payloads and appends virtual peripheral metadata so downstream consumers can attribute composite gestures to their definitions ([context emission helper](src/heart/peripheral/core/event_bus.py#L187-L206)).
1. When a definition is updated or removed, the manager unbinds subscriptions and calls `shutdown()` on the detector, giving implementations a chance to release cached state ([shutdown hook](src/heart/peripheral/core/event_bus.py#L645-L668)).

## Built-in Detectors

- **Double Tap** – Tracks the most recent press per producer and emits a composite event when another press lands within the configured window, returning both raw events for diagnostics ([detector implementation](src/heart/peripheral/core/event_bus.py#L729-L768), [event payload assembly](src/heart/peripheral/core/event_bus.py#L893-L917)).
- **Simultaneous** – Maintains rolling windows of recent events by type and emits when enough distinct producers report within the shared window, tagging the aggregated events and clearing the queue after firing ([detector implementation](src/heart/peripheral/core/event_bus.py#L771-L821), [aggregation helpers](src/heart/peripheral/core/event_bus.py#L920-L946)).
- **Sequence** – Advances through a list of `SequenceMatcher` steps, enforcing optional timeouts per producer and outputting the matched sequence once all predicates succeed ([detector implementation](src/heart/peripheral/core/event_bus.py#L823-L891), [result handling](src/heart/peripheral/core/event_bus.py#L949-L976)).
- **Gated Mirror** – Mirrors events from one producer to another only while a gate predicate evaluates truthy, allowing mode switches or safety interlocks to mediate mirrored outputs ([detector implementation](src/heart/peripheral/core/event_bus.py#L685-L727), [mirror emission](src/heart/peripheral/core/event_bus.py#L991-L1012)).

These helpers encapsulate common gesture patterns while keeping detectors stateless outside their cached history. Each uses the shared context to emit enriched payloads, so consumers can store both the raw gesture sequence and the peripheral metadata for later analysis ([context emission helper](src/heart/peripheral/core/event_bus.py#L187-L206), [double tap payloads](src/heart/peripheral/core/event_bus.py#L752-L756), [simultaneous payloads](src/heart/peripheral/core/event_bus.py#L805-L816), [sequence payloads](src/heart/peripheral/core/event_bus.py#L858-L868)).

## Next Steps

- **Persistence and Discovery** – Persist registered definitions in configuration files so deployments can replay known virtual peripherals on startup and report supported gestures through introspection endpoints ([registration steps](src/heart/peripheral/core/event_bus.py#L600-L643)).
- **State Store Recipes** – Publish reference implementations that leverage `VirtualPeripheralContext.state_store` for shared debouncing or cross-detector coordination, clarifying when detectors should read prior state versus relying solely on event streams ([context state store](src/heart/peripheral/core/event_bus.py#L180-L206)).
- **Runtime Telemetry** – Extend manager logging to emit structured metrics when detectors fire or drop events due to window expirations, easing validation under load and enabling dashboards to track gesture accuracy over time ([routing callback](src/heart/peripheral/core/event_bus.py#L632-L682), [detector payload hooks](src/heart/peripheral/core/event_bus.py#L804-L868)).
- **Playlist Interop** – Document and prototype flows where event playlists trigger or gate virtual peripherals, aligning timing constructs with composite detectors to build richer automation scenarios ([playlist execution](src/heart/peripheral/core/event_bus.py#L322-L520), [detector integrations](src/heart/peripheral/core/event_bus.py#L685-L816)).

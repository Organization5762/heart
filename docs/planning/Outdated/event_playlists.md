# Event Playlist Rollout Plan

## Problem Statement

Coordinate adoption of the event playlist scheduler and new virtual peripheral aggregators so timed behaviours and composite gestures migrate from ad-hoc timers to the shared event bus without destabilising existing peripherals.

## Materials

- `src/heart/peripheral/core/event_bus.py`
- `tests/peripheral/test_event_bus.py`
- Runtime logs capturing `event.playlist.*` emissions
- Access to at least one configuration profile that exercises multiple peripherals

## Opening Abstract

The event playlist manager introduces a declarative way to express timed sequences of `Input` events, while virtual peripherals let us stitch multiple raw inputs into higher-level gestures (double taps, simultaneous presses, input codes) on the same bus. This plan sequences discovery, integration, and validation so applications can compose complex behaviours by wiring playlists and aggregators into their existing handlers. The rollout focuses on defining reusable playlists, layering gesture detectors that emit enriched events, teaching subsystems how to react to lifecycle emissions, and verifying that interrupts and composite detections behave predictably under load.

## Success Criteria

| Behaviour | Validation Signal | Owner |
| --- | --- | --- |
| Playlists trigger sequences deterministically | `tests/peripheral/test_event_bus.py::test_playlist_manual_start_runs_to_completion` passes and emits the expected telemetry payloads | Firmware/Runtime Team |
| Interrupt events halt active playlists safely | `event.playlist.stopped` data shows `reason="interrupted"` with matching payload when `stop.sequence` is emitted in integration testing | Controls Team |
| Applications consume playlist lifecycle data | Logging integration captures `event.playlist.created` and custom completion events for at least one production configuration | Runtime Operations |
| Virtual peripherals emit enriched gestures | `tests/peripheral/test_event_bus.py::test_virtual_double_tap_emits_enriched_payload` and `::test_sequence_virtual_peripheral_detects_konami_code` produce the expected metadata envelopes | Input Systems Team |

## Task Breakdown

### Discovery

- [ ] Catalogue existing timers in rendering and peripheral pipelines that can be replaced by event playlists.
- [ ] Identify physical inputs that should emit composite gestures (double taps, simultaneous presses, command codes) and map them to virtual peripheral definitions.
- [ ] Review `EventPlaylist`, `PlaylistStep`, `EventPlaylistManager`, and `VirtualPeripheralManager` APIs to confirm they cover timing and aggregation needs (offsets, repeats, interrupts, metadata, gesture windows).
- [ ] Inspect `tests/peripheral/test_event_bus.py` to understand expected lifecycle emissions, completion semantics, and gesture metadata envelopes.

### Implementation

- [ ] Define reusable playlists for colour cycling, sensor sampling bursts, and notification banners in configuration modules.
- [ ] Register double-tap, simultaneous, and sequence-based virtual peripherals with enriched metadata so downstream consumers can distinguish gesture types.
- [ ] Replace direct timer usage with `EventBus.playlists.start()` calls, using completion events to trigger downstream transitions.
- [ ] Wire virtual peripheral outputs into existing mode controllers to replace bespoke gesture parsing.
- [ ] Register interrupt events (for example, user input or safety sensors) so long-running playlists can stop without lingering threads.
- [ ] Persist playlist and virtual peripheral handles or definitions in configuration files to enable cross-process reuse.

### Validation

- [ ] Extend integration tests to subscribe to `event.playlist.created/emitted/stopped` and assert the payload schema.
- [ ] Capture sample payloads from virtual peripherals (double tap, simultaneous detection, Konami sequence) and ensure metadata is preserved in logging pipelines.
- [ ] Run hardware-in-the-loop sessions to confirm interrupts fire under physical input (switch rotation, emergency stop buttons) and that gesture windows respect physical timing.
- [ ] Monitor CPU usage during concurrent playlist executions and active gesture detectors to ensure the scheduler thread model scales.
- [ ] Review runtime logs for missing completion events, unexpected cancellation reasons, or gesture spam caused by noisy sensors.

## Narrative Walkthrough

Discovery starts with an audit of existing timing constructs—manual `time.sleep` loops, `threading.Timer` invocations, and update ticks baked into renderers. Each candidate is mapped to an `EventPlaylist` that describes offsets, repeat cadence, and metadata so observers can reason about the sequence. Once the API coverage is confirmed, configuration authors define playlists alongside existing mode registration code, storing the returned `PlaylistHandle` for reuse.

Implementation replaces per-feature timers with event-driven launches. For example, the colour fade feature creates a `PlaylistStep` with a one-second interval and 60 repeats, then uses `EventBus.playlists.start()` when a mode change event lands. Interrupts wire safety signals—if a switch press or heart-rate anomaly occurs, the manager broadcasts `event.playlist.stopped` so renderers can abort gracefully. In parallel, teams author virtual peripherals: a button double tap combines two presses within 500 ms, a simultaneous detector watches for multi-sensor agreement inside 10 ms, and the Konami listener validates control sequences before emitting a higher-level `konami.activated` event. Metadata attached to both playlists and virtual peripherals allows dashboards to tag runs by feature, enabling richer diagnostics.

Validation closes the loop with layered testing. Unit tests cover lifecycle behaviour, while integration tests assert that playlist telemetry reaches log pipelines. During hardware sessions, engineers trigger interrupts to confirm the manager cancels threads promptly and that completion events only fire on successful runs. Performance monitoring verifies that concurrent playlists do not starve the main loop.

## Visual Reference

| Time (s) | Event | Notes |
| --- | --- | --- |
| 0.0 | `event.playlist.created` (`playlist_id=abc123`) | Triggered by `start.sequence` input |
| 0.0 | `color.update` repeat index 0 | `event.playlist.emitted` payload includes metadata |
| 0.75 | `button.double_tap` | Virtual peripheral emits enriched payload referencing `virtual_peripheral.name` |
| 1.0 | `color.update` repeat index 1 | Sequence continues with same playlist ID |
| 3.2 | `stop.sequence` interrupt | Manager signals `runner.stop("interrupted")` |
| 3.2 | `event.playlist.stopped` | `reason="interrupted"`, carries interrupt payload |

| Window (ms) | Raw Inputs | Virtual Peripheral Output |
| --- | --- | --- |
| 5 | `sensor.trigger` from producer 1 and 2 | `sensor.combo` with `events` describing both sources |
| 500 | `button.press` twice from producer 1 | `button.double_tap` with metadata `{gesture: double}` |
| 800 | Ten `button.press` codes matching Konami sequence | `konami.activated` payload with `sequence` field |

## Risk Analysis

| Risk | Probability | Impact | Mitigation | Early Signals |
| --- | --- | --- | --- | --- |
| Playlists leak threads on cancellation | Medium | High | Use `EventPlaylistManager.join()` in shutdown paths and verify `_finalize_run()` always removes run IDs | `event.playlist.stopped` missing after interrupts |
| Incorrect offsets cause drift between renderers and peripherals | Medium | Medium | Add configuration linting that validates offsets and repeat intervals before deployment | Telemetry shows unexpected `offset` values |
| Excessive playlist or gesture metadata bloats state store | Low | Medium | Encourage storing lightweight identifiers and defer large payloads to downstream data stores | State snapshot shows large payload sizes |
| Interrupt storms or gesture flapping starve normal event processing | Low | High | Rate-limit interrupt subscriptions, debounce gestures, or collapse redundant stop events in future revisions | Logs show rapid alternating `created`/`stopped` or gesture bursts |
| Misconfigured gesture windows miss legitimate inputs | Medium | Medium | Exercise detectors in hardware loops and adjust `window`/`timeout` constants per device | QA sessions report missed combos despite correct input |

### Mitigation Checklist

- [ ] Add monitoring to alert when `event.playlist.stopped` is absent for more than 5 seconds after `created`.
- [ ] Document recommended offset ranges and repetition limits for playlist authors.
- [ ] Provide a guideline on metadata payload size (\<1KB) for runtime operators.
- [ ] Prototype interrupt debouncing if hardware generates high-frequency stop signals.
- [ ] Publish reference windows and timeout guidance for virtual peripheral authors, including physical input tolerances.

## Outcome Snapshot

When the plan completes, timed behaviours across renderers and peripherals launch via declarative playlists. Lifecycle events feed logging and analytics, interrupts terminate sequences cleanly, and gesture detectors emit higher-level events whenever users double tap, press in unison, or enter command codes. Teams share a consistent API for composing complex reactions without bespoke timers or ad-hoc input parsers.

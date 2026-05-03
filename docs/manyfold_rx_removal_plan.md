# Manyfold RX Removal Plan

This note breaks down the broad refactor sets needed to remove direct
`manyfold.rx` usage from `main`.

Current count:

- Total: 179 `manyfold.rx` import/use lines across 86 files
- Source: 157 lines across 75 files
- Tests: 22 lines across 11 files

Source breakdown:

- `src/heart/renderers`: 83 lines across 44 files
- `src/heart/peripheral`: 55 lines across 26 files
- `src/heart/utilities`: 19 lines across 5 files

## Goal

Remove direct imports from `manyfold.rx` outside a small compatibility layer, then
remove that layer once all runtime code consumes the replacement stream API.

The important end state is not only "no import strings remain"; the code should
also stop exposing Manyfold RX types in public Heart APIs. Otherwise the next
implementation swap will still force broad renderer and peripheral churn.

## Refactor Set 1: Add A Heart-Owned Reactive Facade

Files involved:

- `src/heart/utilities/reactive.py`
- `src/heart/utilities/reactive_threads.py`
- `src/heart/utilities/reactive_coalescing.py`
- `src/heart/utilities/reactive_instrumentation.py`
- `src/heart/utilities/reactive_streams.py`
- `src/heart/utilities/reactive_stream_settings.py`
- `src/heart/utilities/reactive_stream_types.py`
- `src/heart/utilities/reactive_testing.py`

Why this comes first:

These files are the lowest-level shared imports. They own scheduling, sharing,
coalescing, and type aliases. A Heart-owned API gives the rest of the tree a
stable import target before any behavioral changes happen.

Work required:

- Create or expand a Heart-owned module such as `heart.utilities.reactive`.
- Re-export the minimum primitives used across the repo: `Observable`, `Subject`,
  `BehaviorSubject`, `Disposable`, `CompositeDisposable`, scheduler types,
  `create`, `empty`, `from_iterable`, `interval`, `just`, `merge`,
  `combine_latest`, `pipe`, and `operators`.
- Move type protocols in `reactive_stream_types.py` to refer to Heart-owned
  aliases.
- Remove the old `heart.utilities.reactivex` import path instead of preserving a
  compatibility shim.
- Keep behavior identical at first. This should be a mechanical import migration.

Acceptance criteria:

- Runtime code imports reactive primitives from Heart-owned modules, not
  `manyfold.rx`.
- The only direct `manyfold.rx` imports are inside the compatibility facade.
- Existing tests pass without stream behavior changes.

## Refactor Set 2: Remove RX Types From Peripheral Core APIs

Files involved:

- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/manager.py`
- `src/heart/peripheral/core/streams.py`
- `src/heart/peripheral/core/providers/__init__.py`
- `src/heart/peripheral/core/input/external_sensors.py`

Why this matters:

Peripheral core is the contract layer. It currently returns and stores
`manyfold.rx` observable and subject types directly. As long as these types leak
from the core, every renderer and provider has to know about the same RX backend.

Work required:

- Introduce Heart-owned stream type aliases or protocols for observable streams,
  subjects, and disposables.
- Change `Peripheral._event_stream`, `Peripheral.event_stream`, manager accessors,
  and `PeripheralStreams` methods to expose Heart-owned stream types.
- Keep graph-node Manyfold integration separate from stream plumbing. Manyfold can
  remain the graph runtime while Heart owns the observable API boundary.
- Update provider base classes so concrete providers do not need backend-specific
  return annotations.

Acceptance criteria:

- No public peripheral core API mentions `manyfold.rx`.
- Peripheral manager tests assert behavior, not concrete RX implementation types.
- Renderers can consume streams through Heart-owned contracts.

## Refactor Set 3: Normalize Peripheral Device Streams

Files involved:

- `src/heart/peripheral/switch.py`
- `src/heart/peripheral/sensor.py`
- `src/heart/peripheral/compass.py`
- `src/heart/peripheral/keyboard.py`
- `src/heart/peripheral/led_matrix.py`
- `src/heart/peripheral/radio.py`
- `src/heart/peripheral/flowtoy.py`
- `src/heart/peripheral/microphone.py`
- `src/heart/peripheral/heart_rates.py`
- `src/heart/peripheral/phone_text.py`
- `src/heart/peripheral/rubiks_connected_x.py`
- `src/heart/peripheral/uwb.py`
- `src/heart/peripheral/providers/acceleration/provider.py`
- `src/heart/peripheral/providers/switch/provider.py`

Why this matters:

These modules are a mix of device drivers, Manyfold graph nodes, and reactive
event-stream producers. Most references should become mechanical imports after
the facade exists, but some modules create subjects, create observables, or depend
on scheduler/disposable details.

Work required:

- Replace direct imports with Heart-owned stream primitives.
- Centralize common graph source patterns for `install_node` implementations:
  subject creation, error routing, retry policy, disposal, and source shutdown.
- Keep Manyfold graph APIs imported only where graph nodes are installed or
  detection nodes are declared. The RX dependency should not be needed just to
  model device event streams.
- For simple providers, convert imports mechanically.
- For long-running device sources, verify disposal behavior explicitly.

Acceptance criteria:

- Device modules still publish the same sensor envelopes and graph routes.
- Source shutdown tests cover subject completion/disposal paths where applicable.
- No peripheral device module imports `manyfold.rx` directly.

## Refactor Set 4: Replace Input Profile RX Plumbing With Heart Streams

Files involved:

- `src/heart/peripheral/core/input/keyboard.py`
- `src/heart/peripheral/core/input/gamepad.py`
- `src/heart/peripheral/core/input/accelerometer.py`
- `src/heart/peripheral/core/input/frame.py`
- `src/heart/peripheral/core/input/debug.py`
- `src/heart/peripheral/core/input/profiles/navigation.py`
- `src/heart/peripheral/core/input/profiles/mandelbrot.py`

Why this matters:

The input profile modules contain the densest behavioral stream composition:
`combine_latest`, `merge`, filtering, mapping, edge detection, and background
scheduling. These are more than import rewrites because their behavior is user
visible.

Work required:

- Move repeated key/gamepad stream helpers into reusable Heart input stream
  utilities.
- Replace direct `manyfold.rx` imports with the facade.
- Consider whether profile outputs should remain live streams or become explicit
  state reducers fed by frame ticks. The reducer model would reduce future
  coupling to RX operators.
- Keep the first pass conservative: preserve current stream semantics, then do
  reducer-style simplification in a separate change if desired.

Acceptance criteria:

- Navigation, Mandelbrot controls, keyboard, gamepad, and frame tick tests pass.
- No direct `manyfold.rx` import remains in `src/heart/peripheral/core/input`.
- Input profile behavior is covered by tests for held buttons, taps, d-pad
  changes, and frame-driven updates.

## Refactor Set 5: Migrate Renderer Provider Streams

Files involved:

- `src/heart/renderers/*/provider.py`
- `src/heart/renderers/*/renderer.py` where reactive streams are consumed
- `src/heart/renderers/stateful.py`
- `src/heart/renderers/water_cube/state.py`

Why this matters:

Renderers are the largest file count: 83 lines across 44 files. Most provider
files use the same pattern: import `manyfold.rx as reactivex`, import `operators as ops`, then compose renderer state from peripheral streams.

Work required:

- Convert provider imports to Heart-owned reactive primitives.
- Move repeated provider composition patterns into helper functions where the same
  shape appears across many renderers.
- Update `stateful.py` and renderer state modules first so provider annotations
  do not keep pulling backend types back in.
- Treat modules with `BehaviorSubject` as state-store migrations, not just import
  migrations. These need a Heart-owned state subject or a plain state holder with
  stream output.

Acceptance criteria:

- No renderer imports `manyfold.rx` directly.
- Provider tests still validate emitted state and not implementation-specific
  subject types.
- Renderers continue to receive the same state updates from peripheral streams.

## Refactor Set 6: Update Tests To Use Heart-Owned Test Utilities

Files involved:

- `tests/display/test_sliding_image_marbles.py`
- `tests/display/test_spritesheet_loop_renderer.py`
- `tests/peripheral/test_event_streams.py`
- `tests/peripheral/test_input_core.py`
- `tests/peripheral/test_switch.py`
- `tests/renderers/test_hilbert_curve_renderer.py`
- `tests/renderers/test_mario_provider.py`
- `tests/renderers/test_yolisten_renderer.py`
- `tests/runtime/test_peripheral_runtime.py`
- `tests/utilities/test_reactive_streams.py`
- `tests/utilities/test_reactive_threads.py`

Why this matters:

Tests currently import Manyfold RX primitives directly for subjects, disposables,
marble tests, and scheduler assertions. If tests keep using backend-specific
types, they will mask leaks in production APIs.

Work required:

- Add test helpers under `tests` or `heart.utilities.reactive.testing` for
  subjects, behavior subjects, disposables, and marble-style assertions.
- Replace test imports with Heart-owned helpers.
- Keep a small set of facade tests that prove the compatibility layer maps onto
  the backend correctly.

Acceptance criteria:

- Production tests do not import `manyfold.rx`.
- Only facade-specific compatibility tests are allowed to mention `manyfold.rx`.
- The final `rg "manyfold\\.rx" src tests` output is either empty or limited to
  the compatibility module and its tests.

## Suggested Sequence

1. Add the Heart-owned facade and migrate `src/heart/utilities`.
1. Migrate peripheral core contracts and providers.
1. Migrate peripheral device modules.
1. Migrate input profile modules with focused behavior tests.
1. Migrate renderer providers in batches.
1. Migrate tests to Heart-owned testing helpers.
1. Decide whether the facade remains as the intentional backend boundary or
   whether the backend can be removed entirely.

## Final Verification

Run these checks at the end of each batch:

```bash
rg -n "manyfold\\.rx" src tests
make test
```

The final target is zero direct `manyfold.rx` matches in normal application and
test code, with any remaining backend references isolated to one compatibility
boundary.

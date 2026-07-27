# State similarity tests

State similarity tests exercise an ordered workflow, project the resulting
program state into strict JSON-compatible data, and render that same state into
an RGB golden. The two checks catch both behavioral drift and visual drift.

## Scenario files

Workflow definitions live in JSON so the input sequence and both expected
outputs are reviewable without running Python. The loader rejects missing or
unknown fields and reports validation failures with JSON-style paths.

```json
{
  "name": "move right twice",
  "kind": "navigation",
  "initial": {"config": {"start": "home"}},
  "actions": [
    {"type": "navigate", "config": {"direction": "right"}},
    {"type": "tick", "config": {"count": 2}}
  ],
  "expected": {
    "state": {"screen": "settings"},
    "screen": {
      "fill": [10, 20, 30],
      "shape": [64, 256, 3],
      "channel_tolerance": 2,
      "max_outlier_fraction": 0.001
    }
  }
}
```

The required top-level fields are `name`, `kind`, `initial`, `actions`, and
`expected`. They mirror Given/When/Then:

- `initial` has exactly one object: `config` for configuration-driven setup or
  `state` for an explicit starting state.
- `actions` is ordered. Each action has exactly `type` and `config`. A `tick`
  action may use a positive integer `count`; adapters can expand it into
  repeated ticks.
- `expected` has exactly `state` and `screen`.

`expected.screen` has a positive `[height, width, 3]` shape and exactly one RGB
encoding:

- `fill`: one `[red, green, blue]` value repeated over the declared shape.
- `pixels`: the complete nested `[height][width][3]` channel values. Its actual
  shape must match the declared shape.
- `rows`: one `[red, green, blue]` value per output row, repeated across the
  declared width. This keeps timeline-style contract goldens compact.

`channel_tolerance` and `max_outlier_fraction` are optional screen fields and
default to zero.

Load a scenario with
`load_state_similarity_scenario("tests/state_similarity/scenarios/example.json")`.
The result contains immutable typed action metadata, canonical expected state,
and a materialized contiguous `uint8` RGB array.

## Execution adapters

Scenario authors only edit JSON. The Python test modules are thin execution
adapters that map each `kind`, initial source, and action type onto real Heart
objects. Add adapter code only when introducing a new production boundary or
action vocabulary.

The projected state is an explicit contract. Include every field needed to
explain the behavior under test, but do not serialize an entire runtime object
implicitly. Dataclasses, enums, string-keyed mappings, sequences, NumPy arrays,
and NumPy scalars are normalized recursively. State arrays retain their full
representation as
`{"dtype": "uint8", "shape": [2, 3], "values": [...]}`. Unsupported values,
non-finite floats, cycles, and non-string mapping keys fail with the path to the
offending field.

An RGB pixel is an outlier when any channel differs by more than
`channel_tolerance`. The assertion passes when the outlier fraction is less
than or equal to `max_outlier_fraction`. Keep both bounds as tight as the
renderer permits; deterministic renderers should normally use the zero
defaults.

## HTML review

Generate self-contained review pages for every scenario:

```console
uv run heart-state-review
```

The command writes an index and one HTML page per scenario to
`tmp/state-similarity-review/`. Each page embeds the rendered RGB output and
canonical state for initialization and after every action. Scene changes are
marked explicitly, and animated transitions include five evenly spaced frame
samples by default.

Review checkpoints replay each action prefix independently. Rendering a
checkpoint therefore cannot mutate a later checkpoint or change the workflow
being compared with the final golden. Transition samples run in their own
replay and do not inject ticks into the tested action sequence.

Use `--output PATH` to choose another destination,
`--transition-frames N` to change the transition sample count, and pass JSON
files or directories to review a subset:

```console
uv run heart-state-review \
  tests/state_similarity/scenarios/navigation_keyboard_right_twice.json \
  --output tmp/navigation-review \
  --transition-frames 8
```

Machine-readable system qualification artifacts can be rendered into additional
contract review pages with `--contract-artifact`:

```console
uv run heart-state-review \
  --contract-artifact tmp/world-coordination.json
```

The contract projector keeps deterministic semantic fields: scenario metadata,
ordered lifecycle events, role-by-failure impact rows, convergence bounds,
negative assertions, explicit public API gaps, and a compact RGB strip. It
intentionally excludes process IDs, command IDs, host paths, timestamps, and
incidental log formatting.

## ManyFold StateMachine gap

ManyFold PR 281 at `3c62dd1` adds the right public surfaces for future
navigation contracts: `machine.commands`, `machine.state.latest`,
`machine.transitions`, `machine.events`, and `flush()`. Do not add Heart tests
around a toy reducer to prove that API. ManyFold owns StateMachine internals.

The Heart-side migration should wait until navigation exposes a real typed
command/reducer boundary for `GameModes` and `MultiScene`. At that point the
existing user-story scenarios can assert the reducer-owned state, ordered
domain transitions, ordered audit events, and final RGB render from the same
workflow. Until then, `snapshot_state()` remains an explicit Heart projection.

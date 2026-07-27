# ManyFold mesh integration

Heart binds its named PubSub topics directly to ManyFold's mesh before any peer
is registered. `ManyfoldNodeRuntime` owns the signer-backed node bootstrap and
the mesh lifetime; it does not own another transport, queue, ACK envelope,
duplicate window, or compatibility layer.

The dependency is pinned to ManyFold commit
`ac6086409736148fc60078d906ceceb498a0ca82`. That is the durable-topic branch
head that supports raw-byte live-latest bindings. A release wheel must be built
from the exact eventual merge commit and qualified after force-installing it
into Heart's environment.

## Topic policy

`HEART_TOPIC_POLICIES` is the executable source of truth and
`topic_policy_manifest()` is its JSON form.

| Topic | Class | Retention bound | Semantic key |
| --- | --- | --- | --- |
| `heart.input.navigation` | Durable append | 256 items, 1 MiB, 10 s | request ID |
| `heart.sensor.external.state` | Durable latest | 128 sources, 2 MiB, 2 s | origin, topic, sensor key |
| `heart.frame_tick` | Live latest | one source, 1 KiB message | origin and topic |
| `heart.rendered_frame` | Live latest | eight sources, 128 KiB message | origin, topic, display ID |
| `heart.microphone.level` | Live latest | eight sources, 4 KiB message | origin, topic, `microphone:default` |
| `heart.input` | Live latest | 128 sources, 16 KiB message | origin, topic, stage, stream, source |
| `heart.lifecycle.*` | Durable append | 256 items/topic, 1 MiB, 30 s | stable transition event ID |

Live-latest topics retain one in-memory slot per semantic source. They write no
journal rows, create no replay backlog, and never enter Raft. Reconnection
resynchronizes only current values. Navigation is append/deduplicated because
each user action matters. External sensor state is latest-per-key and expires
because an old physical reading is not current state.

Raft accepts only `heart.world.device.put` and `heart.world.mode.select`.
Frames, ticks, audio, navigation, sensors, and debug data are rejected by the
world projection.

## Observable transitions

Heart reads transport state only through ManyFold's public
`MeshLifecycleEvent`, `MeshLifecycleHealth`, mesh/peer health, and durable-topic
diagnostics. ManyFold owns runtime, peer, durable enqueue/coalesce/drop/expire,
retry/send/ACK/replay, watermark, and terminal-failure transitions.

Heart publishes only domain state that the mesh cannot infer:

- peripheral attached/detached and input source active/inactive;
- scene selected/activated/deactivated;
- renderer started/stopped/failed;
- sensor online/stale/offline;
- frame and audio pipeline pressure/recovery.

Domain events use named `heart.lifecycle.*` topics, stable entity IDs and reason
enums, correlation IDs, and per-entity revisions. Pressure and recovery are
edge-triggered: repeated slow frames or repeated audio overflow statuses do not
create hot-path event streams.

External sensor state becomes stale after 2 seconds and offline after 4 seconds.
Offline state removes the reading from the visible projection.

## Configuration

Set `HEART_MANYFOLD_CONFIG` to the signer-enrolled JSON bootstrap file. Leaving
it unset disables the distributed runtime without starting workers. The config
requires `state_directory`; per-peer delivery journals live beneath its
`delivery` directory.

Production peers use mutual TLS acquired from `MachineSignerService`. Loopback
insecure transport is used only by the exact-wheel qualification fixture.
Signer state, SWIM keys, and enrollment material are deployment secrets.

The RGB matrix implementation is an optional standalone dependency pinned at
`f62c3cedc54d74a3e950d15efe356ca000b7756b`. Non-hardware qualification and
smoke runs must set:

```sh
HEART_PI5_MATRIX_BACKEND=simulated
```

No test or runtime path should assume the removed vendored Rust driver exists.

## Shared exact-wheel qualification

Heart exposes one JSONL supervisor:

```sh
.venv/bin/heart-manyfold-qualification-fixture
```

Pass it to ManyFold's shared distributed gate as the consumer fixture. The gate
owns seeds, scenario order, deadlines, signals, network/storage faults,
resource sampling, lifecycle normalization, and invariant evaluation. Heart
only starts real roles, applies semantic stimuli, reports public state, restarts
or gracefully leaves a requested role, and closes processes.

The topology uses three persistent coordinator roles and a single-failure-
tolerant ring containing redundant navigation ingress plus sensor, renderer,
audio, and pixel roles. Every role binds the production topics before opening
its two real TCP mesh links.

```sh
uv run manyfold-distributed-qualification \
  --profile release \
  --seed 5762 \
  --consumer-fixture-executable \
    "$PWD/.venv/bin/heart-manyfold-qualification-fixture" \
  --consumer-fixture-python "$PWD/.venv/bin/python" \
  --consumer-fixture-working-directory "$PWD" \
  --output-dir .artifacts/manyfold-exact-wheel
```

The candidate ManyFold wheel must already be force-installed in Heart's venv.
The fixture reports its PEP 610 direct URL and SHA-256 wheel digest. The gate
writes the reproducible impact report and raw/semantic lifecycle traces.

## Upstream API gaps

These gaps remain release blockers and are returned by `describe`/`observe`:

1. `LIVE_LATEST` replacement identity omits `origin_node_id`; different nodes
   using the same stable source key overwrite one another downstream.
1. A remotely bound PubSub row does not expose `origin_node_id`; Heart therefore
   cannot publicly observe the full origin/topic/source coalescing identity.
1. `LIVE_LATEST` has no typed coalesce/resync/pressure lifecycle events or
   public counters; exact frame/audio recovery cannot be proven without private
   state.
1. StateMachine commit `3c62dd1` is not based on durable-topic commit
   `ac608640`; Heart cannot pin one exact upstream commit and use both APIs.

Heart does not fill these gaps with payload aliases, private-state inspection,
or a duplicate transport status model.

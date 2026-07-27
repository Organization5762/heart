# Heart consumer qualification fixture v1

Heart exposes an executable JSONL supervisor for ManyFold's exact-wheel
consumer gate:

```sh
.venv/bin/heart-manyfold-qualification-fixture
```

ManyFold owns scenario ordering, deadlines, process and network faults, storage
damage, resource sampling, event normalization, and invariant evaluation.
Heart starts real application-role processes and reports their public state. It
does not implement fault scenarios or inspect ManyFold private state.

## Launch contract

The gate launches the supervisor with its working directory set to the Heart
checkout. It sanitizes the environment and supplies only:

- `MANYFOLD_QUALIFICATION_CANDIDATE_PYTHON`;
- `MANYFOLD_QUALIFICATION_OUTPUT_DIR`;
- `MANYFOLD_QUALIFICATION_SEED`; and
- `PYTHONUNBUFFERED=1`.

The candidate ManyFold wheel must already be force-installed in Heart's
environment. Every role is launched with the candidate Python supplied by the
gate. `describe` reports the installed distribution version, PEP 610 direct URL,
and wheel SHA-256 when the installation originated from a wheel.

Run the shared gate with:

```sh
HEART_PI5_MATRIX_BACKEND=simulated \
  uv run manyfold-distributed-qualification \
  --profile release \
  --seed 5762 \
  --consumer-fixture-executable \
    "$PWD/.venv/bin/heart-manyfold-qualification-fixture" \
  --consumer-fixture-python "$PWD/.venv/bin/python" \
  --consumer-fixture-working-directory "$PWD" \
  --output-dir .artifacts/manyfold-exact-wheel
```

## Framing

The supervisor reads one UTF-8 JSON object per stdin line and writes exactly one
response per stdout line. Diagnostics go to stderr.

```json
{
  "schema_version": 1,
  "request_id": 1,
  "operation": "describe",
  "payload": {}
}
```

Successful responses repeat the schema version and request ID:

```json
{
  "schema_version": 1,
  "request_id": 1,
  "ok": true,
  "value": {}
}
```

Failed responses contain `error.type`, `error.message`, and the public API gaps
that prevent exact-wheel qualification. A response contains exactly one of
`value` or `error`.

## Operations

### `describe`

`describe` returns:

- `consumer: "heart"`;
- candidate-wheel provenance;
- stable `role_id`, `role_kind`, and `node_id` values;
- topic contracts, including delivery class, key, TTL, bounds, and Raft use;
- supported capabilities; and
- unresolved public API gaps.

The required role kinds are:

- `coordinator`;
- `navigation_input_ingress`;
- `low_rate_sensor_ingress`;
- `renderer`;
- `audio_processor`; and
- `pixel_sink`.

The required delivery classes are `durable_append`, `durable_latest`,
`volatile_latest`, and `raft_state`. A volatile topic must report
`retains_journal_rows: false` and `raft: false`.

### `start`

The gate creates and owns every role's configuration, state, journal, and Raft
directory. The `start` payload supplies:

- the deterministic seed and deadline;
- every role's identity and owned paths;
- a per-role `HEART_MANYFOLD_CONFIG` JSON path;
- explicit coordinator members, loopback ports, and Raft state paths; and
- the lifecycle batch limit.

Each generated role configuration contains `schema_version`, `role_id`,
`role_kind`, `node_id`, `cluster_id`, `state_directory`, and
`journal_directory`. Heart treats these values as authoritative.

Heart starts nine real processes: three coordinators, two navigation ingress
roles, and one sensor, renderer, audio, and pixel role. Every process binds the
production topic contracts before opening its two real TCP mesh links. `start`
returns `ready: true` plus each role's process ID, node ID, state directory,
journal directory, and lifecycle cursor.

### `stimulus`

A stimulus has stable, golden-safe identifiers:

```json
{
  "operation_id": "navigation-0001",
  "kind": "navigation",
  "target_role": "navigation-secondary",
  "payload_label": "right",
  "value": {"direction": "right"}
}
```

Supported kinds are `navigation`, `sensor_sample`, `world_write`,
`device_write`, `frame_tick`, `render_frame`, `audio_sample`, and
`debug_input`.

Navigation uses its operation ID as the durable append/deduplication key.
Low-rate sensor state uses durable latest with TTL. Frame ticks, rendered
frames, audio, and debug use live latest and never enter a journal or Raft.
World and device writes use valid Heart commands in ManyFold's persistent Raft
coordinator.

Rendered-frame and audio qualification payloads use the same raw-byte PubSub
boundary as production. There is no envelope, base64 encoding, payload
`key_field`, `DurableDelivery`, or manual ACK layer.

### `observe`

`observe` returns:

- per-role serving state, lifecycle cursor, state revision and digest, sensor
  status and age, and queue depth;
- semantic operations with status, committed ID, and apply count;
- externally visible effects keyed by role, operation, and payload label;
- complete public lifecycle batches;
- public durable-topic diagnostics; and
- unresolved API gaps.

Lifecycle events in `(cursor_before, cursor_after]` must be complete, strictly
ordered, and contiguous. Heart obtains them through ManyFold's public lifecycle
API. It does not reconstruct transport transitions or inspect transport
internals.

State digests, committed IDs, operation IDs, and payload labels are
deterministic. PIDs, ports, clocks, generated transport IDs, and filesystem
roots are measurements and are excluded from golden semantics.

### Role lifecycle

- `restart_role` restarts the requested real role and returns its new handle.
- `graceful_leave` closes one role and returns `left: true, exited: true`.
- `close` closes all remaining roles and returns `clean: true`, final role exit
  states, and final lifecycle batches.

ManyFold lifecycle sequences are node-process-local and non-durable. An
explicit `restart_role` therefore establishes a new lifecycle sequence whose
cursor may start at zero. The gate validates continuity within each process
handle and resets its expected cursor at the restart boundary; Heart does not
rewrite, offset, or persist ManyFold sequence numbers.

The v1 gate drives:

```text
describe -> start -> stimulus* -> observe ->
restart_role(pixel) -> stimulus(newest frame) -> observe -> close
```

## Gate assertions and artifacts

The gate validates all six required role kinds and all four delivery classes.
It rejects journal or Raft retention for volatile topics, lifecycle sequence
gaps, any operation with `apply_count > 1`, an incorrect pixel restart, or an
unclean role exit.

Once ManyFold exposes per-topic `retained_items` and `logical_storage_bytes`
through the mesh's public diagnostics, the gate must additionally require zero
for every live-latest hot topic. Durable sensor state must retain no more items
than its semantic source count and no more than 2 MiB of logical storage. The
pinned mesh head does not expose those fields, so Heart reports the omission as
an API gap instead of inspecting the journal or constructing a parallel
`DurableDelivery`.

Exact-wheel qualification also exposed `RuntimeError("Already borrowed")` when
bound PubSub delivery and publication overlapped in the nine-process topology.
Heart reports that upstream failure directly. It does not serialize publication
behind a Heart lock, retry it through a Heart queue, or add another transport.

It writes:

- `consumer-fixture.jsonl`, the complete request/response trace; and
- `consumer-impact.json`, the normalized role, topic, lifecycle, deduplication,
  restart, and shutdown verdict.

ManyFold may add faults around this protocol without adding scenario operations
to Heart. Heart-specific failure expectations are recorded in
[the role-failure impact matrix](manyfold_role_impact_matrix.md).

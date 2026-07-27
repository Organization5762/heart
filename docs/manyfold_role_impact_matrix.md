# ManyFold role-failure impact matrix

This matrix is the Heart-specific assertion layer consumed by ManyFold's shared
exact-wheel gate. ManyFold owns fault injection and writes the reproducible
trace artifacts; Heart exposes the public observations used below.

| Failed role | Unaffected roles | Expected application impact | Public evidence |
| --- | --- | --- | --- |
| Coordinator leader | Mesh ingress, renderer, audio, pixel continue serving | A new leader commits; world/device revision and digest survive | coordinator status and committed-log revision/digest |
| Navigation ingress | Other ingress and all non-input roles continue | Stable operation retries apply once; no duplicate navigation effect | operation ID, committed ID, apply count, visible scene effect |
| Low-rate sensor ingress | Navigation, renderer, audio, pixel continue | Last value becomes stale, then offline; expired data is not visible | sensor status, stale age, sensor lifecycle sequence |
| Renderer | Navigation, sensor, audio, pixel continue | Render degradation is local; frame data has no durable/Raft rows | serving flags, renderer lifecycle, topic diagnostics |
| Audio processor | Navigation, sensor, renderer, pixel continue | Audio degradation is local; audio samples have no durable/Raft rows | serving flags, audio pipeline lifecycle, topic diagnostics |
| Pixel sink | Producers and other roles continue | Restart sees only the newest rendered-frame label | pixel user effect plus zero rendered-frame journal rows |

The required disconnect story is:

```text
disconnect -> bounded enqueue/coalesce/expire -> reconnect ->
replay or current-value resync -> sender ACK -> clean shutdown
```

Navigation uses durable append/deduplication. Sensors use durable latest plus
TTL. Frames and audio use one-slot live latest and therefore resynchronize
current state rather than replaying history. World/device state is Raft-backed.

The shared gate writes:

- `durable-topics/impact-report.json`;
- `lifecycle-events.raw.jsonl`;
- `lifecycle-events.semantic.jsonl`;
- `api-gaps.json`.

Golden semantics use role IDs, operation IDs, payload labels, lifecycle kinds,
reasons, and revisions. PIDs, ports, clocks, generated message IDs, and
filesystem roots are measurements only.

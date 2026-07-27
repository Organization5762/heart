# ADR 0001: Manyfold ownership boundaries

- Status: Accepted
- Date: 2026-07-26
- Owners: Heart and Manyfold maintainers

## Context

Heart uses Manyfold at three distinct levels: application streams, a
process-local graph, and a distributed node runtime. Similar vocabulary at
these levels made it easy to imply duplicate owners or to treat migration
adapters as new framework code.

The supported package contract is Manyfold 0.1.42. The dependency declaration
in [`pyproject.toml`](../../pyproject.toml) and its exact resolution in
[`uv.lock`](../../uv.lock) are authoritative:

| Checkpoint | Revision | Meaning |
| --- | --- | --- |
| Canonical A2 checkout | `726f64d72b36d8bd134bda63e29ebd80472736b6` | The clean local canonical worktree is pin-identical. The resolved A1 feature branch is `630c575`, whose parent is this revision and whose five-file commit preserves the recovered interface work. Neither ref is the current Heart pin. |
| Current Heart dependency | `89c1c8b01cfee1785cbdc7c72cc3876b61b7b8a7` | The supported 0.1.42 revision recorded by the dependency declaration and lockfile. |

## Decision

Ownership follows construction and policy:

| Boundary | Heart owns | Manyfold owns |
| --- | --- | --- |
| Streams | Domain route/topic schemas, semantic keys, retention and delivery policy, concrete bounds, and thin application adapters such as `GraphRouteStream`. | Subscription/value contracts, operators, publication, observation, and retention/delivery enforcement and diagnostics. |
| Graph | The application composition root. `PeripheralManager` constructs the production peripheral graph, installs Heart nodes, retains their handles, and disposes them in reverse order. | Graph topology, routing, storage, backpressure, observation, and managed execution primitives. |
| Managed graph node | Node bodies, hardware resources, routes, configuration, and concrete retry/backoff policy. The Heart installer retains the returned handle. | `ManagedGraphNode` policy enforcement, stop token, worker loop, control subscription, and handle disposal mechanics. |
| Process node runtime | One `ManyfoldNodeRuntime` per Heart process, runtime configuration, topic policy, `TransportMesh` composition, startup before peripheral detection, bounded foreground polling, and process shutdown. | Canonical `NodeRuntime` signer acquisition, authenticated bootstrap, discovery, membership, SWIM, reconnect, snapshots, and internal resource shutdown; `TransportMesh` owns mesh transport mechanics. |

A component that constructs a graph, subscription, managed-node handle, or
runtime resource must dispose it. Borrowing adapters must not close resources
owned by their caller. The current `PeripheralManager.stop()` disposes input
subscriptions and managed-node handles but does not call `Graph.dispose()`.
That is an explicit lifecycle gap; this ADR does not treat manager shutdown as
complete graph cleanup until focused code and tests close it.

Isolated tests and tools may construct and own a whole graph. Production
adapters must receive the application graph. The fallback graph constructors in
`AccelerometerInput` and `ExternalSensorInput` are migration debt, not supported
precedent; they may not proliferate and should disappear in the planned graph
consolidation.

The method assignments to `RoutePipeline` in
[`streams.py`](../../src/heart/peripheral/core/streams.py) are migration shims:
they translate existing Heart calls to Manyfold observables and retain no
runtime state. They do not transfer generic operator ownership to Heart. New
operators and reusable execution behavior belong in Manyfold, followed by an
intentional Heart pin update.

`ManyfoldNodeRuntime` does not own the peripheral graph, and
`PeripheralManager` does not own discovery, membership, SWIM, or mesh worker
lifecycle. High-rate frame, microphone, and debug paths remain outside durable
delivery and Raft as documented in
[`manyfold_node_runtime.md`](../manyfold_node_runtime.md) and
[`world_coordination.md`](../world_coordination.md).

## Consequences

- Heart policy remains visible at its composition roots; Manyfold machinery has
  one reusable implementation.
- Tests that change a boundary must exercise the real pinned Manyfold
  implementation and the owning Heart lifecycle.
- A Manyfold pin change requires reviewing this ADR, the node-runtime
  qualification, and the stream/graph integration slice.
- Compatibility aliases, runtime version probes, and duplicate Heart
  transports are unsupported.

This decision describes the current Heart baseline at Manyfold revision
`89c1c8b01cfee1785cbdc7c72cc3876b61b7b8a7`. Later graph-consolidation or
durable-ownership decisions must supersede this ADR rather than silently
changing its ownership claims.

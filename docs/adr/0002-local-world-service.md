# ADR 0002: Local World service

- Status: Accepted
- Date: 2026-07-26
- Owners: Heart maintainers
- Supersedes: The World ownership decision in
  [ADR 0001](0001-manyfold-ownership-boundaries.md)

## Context

Heart's World model was implemented as a distributed Raft projection with
typed RPC and durable command delivery, but no production caller required
cross-process World coordination. The implementation and its qualification
surface introduced transport, consensus, request-ID, retry, deduplication, and
artifact-rendering ownership that the product did not use.

## Decision

`World` is a process-local typed service. It owns device records, active-mode
selection, and an immutable revisioned snapshot under one lock. Device IDs,
positions, dimensions, and capability tuples are validated before mutation.
Rejected operations leave both state and revision unchanged, while idempotent
operations do not advance the revision.

The service retains at most 256 devices. This is a deliberate process-memory
bound above Heart's expected physical fleet size; replacing a registered device
at capacity remains valid. Cross-process World coordination requires a new
decision based on a concrete production caller and its consistency,
availability, and recovery requirements.

The unused Raft/RPC/durable implementation, executable proof, projector, CLI
option, tests, golden artifact, and current-behavior documentation are retired.
World owns no Manyfold graph, route, managed node, RPC, Raft, or durable-delivery
lifecycle.

## Consequences

- World behavior and failure modes are visible as ordinary local domain
  operations.
- State cardinality and mutation atomicity have focused regression coverage.
- Heart no longer presents a distributed World qualification contract that the
  runtime does not exercise.
- A future distributed design must establish an immediate caller and supersede
  this decision explicitly.

# Reactive stream coalescing modes

## Question

How can the reactive event stream flow control reduce burst load while still
allowing low-latency updates for the first event in a burst?

## Materials

- Access to runtime environment configuration.
- Ability to review reactive stream flow-control implementation code.

## Context

High-frequency peripherals can emit bursts where downstream consumers benefit
from receiving the first update quickly, followed by a consolidated trailing
update once the burst settles.

## Findings

- The shared stream coalescing operator now supports a leading mode that emits
  the first payload immediately, while still delivering the latest payload at
  the end of the configured coalescing window when more data arrives.
- The coalescing mode is configurable so deployments can choose between purely
  trailing updates (`latest`) and leading-plus-trailing updates (`leading`).

## Relevant sources

- `src/heart/utilities/reactivex_streams.py` (coalescing operator implementation)
- `src/heart/utilities/env.py` (configuration entry points and enums)
- `docs/reactivex_streams.md` (runtime tuning guidance)
- `tests/utilities/test_reactivex_streams.py` (flow-control test coverage)

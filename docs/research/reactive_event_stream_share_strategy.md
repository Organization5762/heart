# Reactive event stream share strategy configuration

## Problem statement

Core reactive event streams currently use a single sharing operator with no way to
configure replay behaviour. Late subscribers may miss the most recent peripheral
events, which complicates diagnostics and can lead to inconsistent initialization
in downstream streams. The lack of configurability also limits experimentation with
buffered replay when tuning for performance and correctness.

## Approach

- Introduce a configurable share strategy for core reactive streams so the event
  bus and peripheral observables can be replayed when needed.
- Default to replaying the latest value to improve debuggability while preserving
  a straightforward `share` option when back-compatibility is desired.
- Support a bounded replay buffer size for scenarios that need a short history for
  late subscribers.

## Configuration

- `HEART_RX_STREAM_SHARE_STRATEGY`
  - `replay_latest` (default): replay the most recent event to late subscribers.
  - `replay_buffer`: replay the last `HEART_RX_STREAM_REPLAY_BUFFER` events.
  - `share`: preserve the pre-existing no-replay share behaviour.
- `HEART_RX_STREAM_REPLAY_BUFFER`
  - Integer buffer size used when the strategy is `replay_buffer`.

## Implementation notes

- `heart.utilities.reactivex_streams.share_stream` wraps the sharing logic and
  provides logging hints for the configured strategy.
- `heart.peripheral.core.Peripheral.observe` and
  `heart.peripheral.core.manager.PeripheralManager.get_event_bus` now use the
  shared helper so configuration applies consistently across core event streams.
- Tests validate that late subscribers receive the configured replay buffer.

## Materials

- `src/heart/utilities/reactivex_streams.py`
- `src/heart/utilities/env.py`
- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/manager.py`
- `tests/utilities/test_reactivex_streams.py`

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
- Allow time-based eviction and delayed auto-connect to keep shared streams
  performant under variable subscriber churn.
- Add a configurable ref-count grace window so replayed streams avoid rapid
  disconnect/reconnect cycles when subscribers churn quickly.
- Gate ref-count connections behind a configurable minimum subscriber threshold
  to avoid waking upstream sources until demand is sufficient.
- Ensure ref-count sharing can connect after the first subscription to avoid
  missing immediate emissions from hot upstream sources, while leaving an eager
  connect mode available when legacy timing is desired.

## Configuration

- `HEART_RX_STREAM_SHARE_STRATEGY`
  - `replay_latest` (default): replay the most recent event to late subscribers.
  - `share_auto_connect`: share without replay while keeping the source
    connected after the first subscriber arrives, avoiding repeated
    subscriptions when observers churn.
  - `replay_latest_auto_connect`: replay the most recent event while keeping the
    source connected after the first subscriber arrives, avoiding repeated
    subscriptions when observers churn.
  - `replay_buffer`: replay the last `HEART_RX_STREAM_REPLAY_BUFFER` events.
  - `replay_buffer_auto_connect`: replay the buffer while keeping the source
    connected after the first subscriber arrives.
  - `share`: preserve the pre-existing no-replay share behaviour.
- `HEART_RX_STREAM_REPLAY_BUFFER`
  - Integer buffer size used when the strategy is `replay_buffer`.
- `HEART_RX_STREAM_REPLAY_WINDOW_MS`
  - Optional millisecond window used to evict old replayed events.
- `HEART_RX_STREAM_AUTO_CONNECT_MIN_SUBSCRIBERS`
  - Integer subscriber count required before auto-connect strategies attach to
    the upstream source.
- `HEART_RX_STREAM_REFCOUNT_GRACE_MS`
  - Integer grace window in milliseconds to delay ref-count disconnection for
    share/replay strategies that would otherwise detach immediately.
- `HEART_RX_STREAM_REFCOUNT_MIN_SUBSCRIBERS`
  - Integer subscriber count required before ref-count strategies connect to
    the upstream source.
- `HEART_RX_STREAM_CONNECT_MODE`
  - `lazy` (default): connect ref-count streams after the first subscriber
    attaches to avoid missing immediate emissions from hot upstream sources.
  - `eager`: connect ref-count streams before the first subscriber attaches,
    matching the previous timing behaviour.

## Implementation notes

- `heart.utilities.reactivex_streams.share_stream` wraps the sharing logic and
  provides logging hints for the configured strategy.
- `heart.utilities.env.Configuration.reactivex_stream_connect_mode` controls
  the ref-count connect timing for shared streams.
- `heart.utilities.env.Configuration.reactivex_stream_refcount_min_subscribers`
  gates ref-count connections for shared streams.
- `heart.peripheral.core.Peripheral.observe` and
  `heart.peripheral.core.manager.PeripheralManager.get_event_bus` and
  `heart.peripheral.core.manager.PeripheralManager.get_main_switch_subscription`
  now use the shared helper so configuration applies consistently across core
  event streams.
- Tests validate that late subscribers receive the configured replay buffer.
- Ref-count grace uses a scheduled disconnect to keep the upstream subscription
  warm during short-lived subscriber churn.

## Materials

- `src/heart/utilities/reactivex_streams.py`
- `src/heart/utilities/env.py`
- `src/heart/peripheral/core/__init__.py`
- `src/heart/peripheral/core/manager.py`
- `tests/utilities/test_reactivex_streams.py`
- `tests/utilities/test_env.py`
- `docs/research/reactive_event_stream_share_strategy.md`

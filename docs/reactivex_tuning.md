# Reactivex tuning

This note documents environment variables that tune ReactiveX flow control and
thread pools. Use them to balance responsiveness and CPU load when peripherals
emit high-frequency events.

## Materials

- Access to the runtime environment where the Heart process starts.
- Permission to set environment variables for the process.

## Stream flow control

- `HEART_RX_STREAM_COALESCE_WINDOW_MS` sets the coalescing window in
  milliseconds for shared streams. Values above `0` emit only the latest payload
  per window, reducing bursty updates. Default: `0` (disabled).
- `HEART_RX_STREAM_STATS_LOG_MS` sets the interval in milliseconds for logging
  per-stream event counts and subscriber totals at debug level. Use this to
  confirm whether streams are idle, saturated, or oversubscribed. Default: `0`
  (disabled).

## Thread pool sizing

Set these environment variables before starting the runtime:

- `HEART_RX_BACKGROUND_MAX_WORKERS` sets the thread count for general ReactiveX
  background work such as peripheral polling and periodic tasks. Default: `4`.
- `HEART_RX_INPUT_MAX_WORKERS` sets the thread count for key input polling and
  controller updates. Default: `2`.

Both values must be integers of at least `1`. Raising the input pool keeps key
input latency predictable when renderers or sensors generate heavy traffic.
Lowering the background pool can reduce CPU contention on constrained hardware.

## Usage notes

- Apply changes by restarting the process so configuration values are reloaded.
- Start with small coalescing windows (for example, `10`–`30` ms) to smooth
  spikes without starving downstream consumers.
- Coalescing windows flush the last pending value on the next emission or
  completion so late timers do not drop updates.
- Enable stream diagnostics only when needed; debug logs can add noise on busy
  systems.

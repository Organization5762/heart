# Reactivex stream flow control

This note documents environment variables that tune reactive stream sharing and
flow control. Use these settings to balance responsiveness and CPU load when
peripherals emit high-frequency events.

## Materials

- Access to the runtime environment where the Heart process starts.
- Permission to set environment variables for the process.

## Stream flow control

- `HEART_RX_STREAM_COALESCE_WINDOW_MS` sets the coalescing window in
  milliseconds for shared streams. Values above `0` emit only the latest payload
  per window, reducing bursty updates. Default: `0` (disabled).

## Stream diagnostics

- `HEART_RX_STREAM_STATS_LOG_MS` sets the interval in milliseconds for logging
  per-stream event counts and subscriber totals at debug level. Use this to
  confirm whether streams are idle, saturated, or over-subscribed. Default: `0`
  (disabled).

## Usage notes

- Apply changes by restarting the process so configuration values are reloaded.
- Start with small coalescing windows (for example, `10`–`30` ms) to smooth
  spikes without starving downstream consumers.
- Overdue coalescing windows flush the last pending value on the next emission
  or completion so late timers do not drop updates.
- Enable stream diagnostics only when needed; debug logs can add noise on busy
  systems.

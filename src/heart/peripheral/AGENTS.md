# Peripheral Agent Instructions

## Timing and clocks
- Use `time.monotonic()` for elapsed-time comparisons such as timeouts, retry
  windows, or input debouncing. Reserve `time.time()` for wall-clock
  timestamps that need to be shared outside the process.
- Define default retry/backoff delays as module-level constants, even when they
  are exposed as constructor defaults, so timing knobs stay discoverable.

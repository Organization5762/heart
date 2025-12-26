# Peripheral Agent Instructions

## Timing and clocks
- Use `time.monotonic()` for elapsed-time comparisons such as timeouts, retry
  windows, or input debouncing. Reserve `time.time()` for wall-clock
  timestamps that need to be shared outside the process.

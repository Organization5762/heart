# Reactivex input thread tuning research note

## Context

Key input peripherals (keyboard, switch, gamepad) use reactivex timers and
subscriptions that can suffer if they share a saturated background thread pool.
We now separate the input scheduler from the background scheduler so operators
can tune them independently.

## Materials

- Runtime configuration via environment variables.
- Source references listed below.

## Findings

- The input scheduler is now isolated so input polling does not contend with
  higher-cost background observables.
- Two environment variables define the worker counts for each pool, allowing
  tuning without code changes.

## Operational guidance

- Increase `HEART_RX_INPUT_MAX_WORKERS` when input latency is visible during
  heavy rendering or sensor workloads.
- Decrease `HEART_RX_BACKGROUND_MAX_WORKERS` when CPU contention is limiting
  input responsiveness on small devices.

## References

- `src/heart/utilities/reactivex_threads.py`
- `src/heart/utilities/env.py`
- `src/heart/peripheral/keyboard.py`
- `src/heart/peripheral/switch.py`
- `src/heart/peripheral/gamepad/gamepad.py`

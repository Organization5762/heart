# Reactivex thread tuning

This note describes the environment variables that tune the shared reactivex thread
pools used by Heart. The goal is to keep key input polling responsive even when
background workloads are busy.

## Materials

- Access to the runtime environment where `totem run` executes.
- Environment variables for reactivex thread counts.

## Configuration

Set these environment variables before starting the runtime:

- `HEART_RX_BACKGROUND_MAX_WORKERS` sets the thread count for general reactivex
  background work such as peripheral polling and periodic tasks. Default: `4`.
- `HEART_RX_INPUT_MAX_WORKERS` sets the thread count for key input polling and
  controller updates. Default: `2`.

Both values must be integers of at least `1`. Raising the input pool lets key
inputs remain responsive when renderers or sensors produce heavy reactivex load.
Lowering the background pool can reduce CPU contention on constrained hardware.

## Usage notes

- Apply changes by restarting the process so the thread pools are rebuilt.
- Keep the input pool small but non-zero to preserve predictable latency for
  key inputs.

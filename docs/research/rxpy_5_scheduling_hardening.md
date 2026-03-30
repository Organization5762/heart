# RxPy 5 Scheduling Hardening

## Problem Statement

Document the scheduler-topology changes made for RxPy 5 so pygame-bound input delivery stays on the game loop thread, blocking peripheral readers stay isolated, and scheduler configuration maps to real runtime behavior.

## Materials

- Local checkout of this repository.
- The runtime and input-layer sources under `src/heart/utilities/`, `src/heart/runtime/`, and `src/heart/peripheral/`.
- The scheduler and input tests under `tests/utilities/` and `tests/peripheral/`.

## Findings

- `src/heart/utilities/reactivex_threads.py` no longer treats `TimeoutScheduler` as a stand-in for the pygame thread. `pipe_in_main_thread()` now enqueues work into an explicit frame-thread handoff queue, and `drain_frame_thread_queue()` runs those callbacks when `src/heart/runtime/peripheral_runtime.py` advances the peripheral runtime on the game loop thread.
- Shared scheduler roles are now explicit and bounded. `background_scheduler()`, `input_scheduler()`, and `blocking_io_scheduler()` are long-lived shared schedulers whose worker counts come from `HEART_RX_BACKGROUND_MAX_WORKERS`, `HEART_RX_INPUT_MAX_WORKERS`, and `HEART_RX_BLOCKING_IO_MAX_WORKERS`.
- The dead `HEART_RX_EVENT_BUS_SCHEDULER` path was removed from `src/heart/utilities/env/reactivex.py` and the related enum export was deleted because the repository no longer applies an event-bus scheduler branch.
- Keyboard and gamepad polling now use the input scheduler for timer emission and the frame-thread handoff for pygame-bound sampling in `src/heart/peripheral/core/input/keyboard.py`, `src/heart/peripheral/core/input/gamepad.py`, and the compatibility layer in `src/heart/peripheral/keyboard.py`.
- Blocking readers moved off the startup path. `src/heart/peripheral/switch.py` subscribes its serial reader on the blocking-IO scheduler, while `src/heart/peripheral/switch.py` and `src/heart/peripheral/sensor.py` now start their long-lived blocking loops on named background threads instead of pinning `PeripheralManager.start()`.
- Input latency instrumentation is lightweight and local. `src/heart/peripheral/core/input/debug.py` records per-stream p50/p95/p99/max latency when payloads carry monotonic timestamps, while `src/heart/utilities/reactivex_threads.py` records frame-thread handoff delay so before-and-after comparisons can include the queue boundary itself.

## Source Map

- Scheduler and frame-thread handoff: `src/heart/utilities/reactivex_threads.py`
- Runtime drain point: `src/heart/runtime/peripheral_runtime.py`
- Input latency tracing: `src/heart/peripheral/core/input/debug.py`
- Keyboard and gamepad polling: `src/heart/peripheral/core/input/keyboard.py`, `src/heart/peripheral/core/input/gamepad.py`, `src/heart/peripheral/keyboard.py`
- Blocking peripherals: `src/heart/peripheral/switch.py`, `src/heart/peripheral/sensor.py`
- Validation: `tests/utilities/test_reactivex_threads.py`, `tests/peripheral/test_switch.py`, `tests/peripheral/test_input_core.py`, `tests/utilities/test_env.py`

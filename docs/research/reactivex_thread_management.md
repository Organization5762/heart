# Centralized reactivex thread management

## Overview

Reactive peripherals currently schedule background polling and IO work with
per-subscription thread creation. This change introduces a shared scheduler so
ReactiVex work runs on a single, named thread pool that is managed in one
place, making thread usage easier to audit and tune.

## Materials

- `src/heart/utilities/reactivex_threads.py`
- `src/heart/peripheral/keyboard.py`
- `src/heart/peripheral/switch.py`
- `src/heart/peripheral/gamepad/gamepad.py`

## Implementation

- `background_scheduler` in `src/heart/utilities/reactivex_threads.py` lazily
  constructs a `ThreadPoolScheduler` backed by a named `ThreadPoolExecutor`.
- Peripheral pollers now request the shared scheduler instead of instantiating
  `NewThreadScheduler` directly, keeping reactivex thread creation centralized.

## Expected impact

Using a shared scheduler reduces scattered thread creation in input peripherals,
while still allowing those observables to run asynchronously. The scheduler is
now the single place to adjust thread pool sizing if future tuning is needed.

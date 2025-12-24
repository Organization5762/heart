# Reactive stream replay window configuration

## Problem

Reactive streams that use replay buffers retain all buffered events indefinitely. This can grow memory usage in long-running sessions and makes it harder to reason about how much history is held for each shared stream. The core sharing utility needed a configurable way to cap the time window for replayed events without changing every stream definition.

## Approach

- Introduce `HEART_RX_STREAM_REPLAY_WINDOW_MS` to cap the replay window used by the shared stream helper.
- Apply the window to all replay-based strategies so the replay buffer expires old entries in a predictable, time-bound way.
- Keep the existing share strategy selection intact so deployments can opt into the new behavior without changing code.

## Configuration

Set `HEART_RX_STREAM_REPLAY_WINDOW_MS` to a positive integer value (milliseconds). Leaving the variable unset keeps the current unlimited replay window behavior.

## Impact

- Scalability improves by limiting how long replay buffers retain events.
- Debuggability improves because a single configuration controls replay history retention.
- No changes are required at call sites; the stream helper applies the window consistently.

## Materials

- `src/heart/utilities/env.py` (configuration entry point for environment settings)
- `src/heart/utilities/reactivex_streams.py` (shared stream helper applying replay settings)

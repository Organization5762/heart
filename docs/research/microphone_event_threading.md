# Microphone event dispatch threading

## Summary

The microphone peripheral was dispatching `Subject.on_next` directly from the
sounddevice audio callback. Because reactive subscriptions are synchronous by
default, downstream I/O (notably WebSocket sends in the runtime) could run on the
callback thread and stall audio capture. The microphone event stream now
schedules notifications onto the shared input scheduler so the callback remains
non-blocking.

## Impacted code

- `src/heart/peripheral/microphone.py` (`Microphone._event_stream`)
- `src/heart/runtime/peripheral_runtime.py` (subscription that may perform I/O)
- `src/heart/peripheral/core/manager.py` (event bus scheduling behavior)

## Materials

- Source inspection of `src/heart/peripheral/microphone.py`
- Source inspection of `src/heart/runtime/peripheral_runtime.py`
- Source inspection of `src/heart/peripheral/core/manager.py`

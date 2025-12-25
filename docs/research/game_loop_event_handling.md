# Game loop event handling helper

## Problem

`GameLoop` owned both the runtime loop and the pygame event handling logic, which made
the core loop harder to scan and hid event-specific responsibilities inside the main
orchestration class.

## Notes

- The pygame event handling has been moved into a dedicated helper so the main loop can
  focus on scheduling peripheral ticks, preprocessing, rendering, and frame pacing.
- The runtime loop now consumes the helper's boolean result to decide when to stop,
  keeping shutdown logic in one place.

## Materials

- `src/heart/runtime/game_loop.py`
- `src/heart/runtime/pygame_event_handler.py`

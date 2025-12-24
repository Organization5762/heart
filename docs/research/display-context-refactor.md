# Display context refactor notes

## Summary

The game loop previously managed pygame display state (screen and clock) directly while also
handling peripheral setup, renderer orchestration, and frame presentation. To make the display
responsibilities clearer, I introduced a dedicated `DisplayContext` that owns initialization and
validation of the screen and clock.

## Rationale

The loop lifecycle mixes several responsibilities. Extracting a display-focused helper makes it
easier to locate where display configuration happens and keeps screen/clock checks in one place.
This keeps the game loop focused on orchestration while the new helper isolates display setup.

## Source references

- `src/heart/runtime/display_context.py`
- `src/heart/runtime/game_loop.py`

## Materials

- `src/heart/runtime/display_context.py`
- `src/heart/runtime/game_loop.py`

# Runtime loop refactor for clarity

## Problem statement

The runtime loop and render pipeline logic are correct but the control flow is dense, which makes it harder to scan for initialization order, per-frame steps, and renderer logging responsibilities.

## Notes

- Broke the game loop into explicit helper steps for initialization, peripheral streaming, and per-frame processing to make the lifecycle easier to follow.
- Extracted renderer frame execution and logging into focused helpers so the render pipeline reads as a sequence of steps instead of a monolithic method.

## Source references

- `src/heart/runtime/game_loop/core.py`
- `src/heart/runtime/render/pipeline.py`

## Materials

- Repository source files listed above.

# Render executor reuse for binary surface merges

## Problem

`GameLoop._render_surfaces_binary` created a new `ThreadPoolExecutor` on every frame. That
per-frame allocation adds thread startup and teardown overhead to a hot loop in the
rendering path.

## Approach

Reuse a single executor instance across frames and shut it down when the game loop exits.
This preserves the existing parallel merge strategy but avoids repeated thread creation.

## Sources

- `src/heart/environment.py` (`GameLoop._render_surfaces_binary`, executor lifecycle)

## Materials

- Python standard library `concurrent.futures.ThreadPoolExecutor` documentation

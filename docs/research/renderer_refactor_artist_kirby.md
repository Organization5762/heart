# Renderer packaging refactor: artist and kirby scenes

## Context

The `ArtistScene` and `KirbyScene` renderers previously lived in single monolithic modules under `src/heart/display/renderers`. That layout made it difficult to share initialization logic or track scene construction inputs.

## Changes

- Introduced dedicated packages (`artist/` and `kirby/`) with `state`, `provider`, and `renderer` modules for each scene collection.
- Providers now assemble the scene lists, keeping asset wiring and configuration isolated from rendering behaviour.
- Renderers are thin `MultiScene` subclasses that consume provider outputs, improving parity with other renderers such as `water_cube` and `life`.

## Impact

The new layout separates responsibilities and makes it easier to swap or extend scene lists without modifying rendering code. Future changes (e.g., new assets or parameterized providers) can be added by adjusting provider construction while keeping rendering behaviour stable.

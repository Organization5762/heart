# L-system renderer refactor

This update restructures the L-system renderer into the provider/state/renderer pattern already used by other animated scenes. The refactor keeps the grammar drawing logic intact while moving the state advancement into an observable provider so the renderer only needs to translate state into pixels.

## Components

- `src/heart/display/renderers/l_system/state.py` keeps the turtle-grammar string and tracks elapsed time between updates.
- `src/heart/display/renderers/l_system/provider.py` advances the grammar whenever a second of simulated time elapses, driven by the shared peripheral clock stream.
- `src/heart/display/renderers/l_system/renderer.py` consumes the current grammar and draws it on the full device surface using the existing turtle rules.
- `src/heart/programs/configurations/l_system.py` now resolves the provider from the shared container and injects it into the renderer.

## Usage notes

The renderer remains in `DeviceDisplayMode.FULL`, so it still renders across the full cube surface. The provider seeds the renderer with an initial grammar immediately, so callers do not need an explicit initialization pass beyond constructing the renderer with the resolved provider.

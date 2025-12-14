# Renderer package split for flame and free text

## Overview

The flame and free text renderers now mirror the provider/state/renderer pattern used by the Water and Life pipelines. Each renderer lives in its own package with discrete modules for state definitions, observable providers, and drawing logic.

## Changes

- `flame` now subscribes to a `FlameStateProvider` that streams time data from `PeripheralManager.game_tick` and forwards it to `FlameRenderer` for blitting cached flame strips.
- `free_text` shifts text wrapping and font sizing into `FreeTextStateProvider` while `FreeTextRenderer` focuses purely on drawing centred lines using streamed state snapshots.

## File layout

- `src/heart/renderers/flame/{provider.py,state.py,renderer.py}`
- `src/heart/renderers/free_text/{provider.py,state.py,renderer.py}`

## Notes

- Providers maintain subscriptions and dispose them on renderer reset to prevent leaked observers.
- Both renderers keep their original visual behaviour while relying on observable state updates instead of in-loop mutation.

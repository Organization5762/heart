# Frame accumulator array strategy tuning

## Problem

`FrameAccumulator.as_array` converts the accumulated surface into an RGB array by
calling `pygame.surfarray.array3d`. That helper copies pixel data every time the
array cache is rebuilt, which becomes noticeable when renderers request arrays
frequently. The current implementation does not provide a way to trade memory
safety for lower per-frame allocation cost.

## Approach

Expose an environment-controlled strategy for array conversion. The default
`copy` strategy keeps the existing behavior by using `array3d`. When `view` is
selected, the accumulator uses `pygame.surfarray.pixels3d` to return a view
into the surface, reducing allocations at the cost of holding a surface lock
for as long as the array view is alive. This allows performance-sensitive
renderers to opt into the faster path while preserving the safer default.

## Configuration

- `HEART_FRAME_ARRAY_STRATEGY=copy` (default) keeps array copies and avoids
  holding surface locks.
- `HEART_FRAME_ARRAY_STRATEGY=view` returns a view into the surface for lower
  allocation overhead.

## Materials

- `src/heart/renderers/internal/frame_accumulator.py` (`FrameAccumulator.as_array`)
- `src/heart/utilities/env.py` (`Configuration.frame_array_strategy`)

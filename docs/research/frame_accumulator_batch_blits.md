# Frame accumulator batched blits

## Summary

`FrameAccumulator.flush` now batches consecutive blit commands into a single
`pygame.Surface.blits` call. This reduces Python-level dispatch overhead when
renderers queue many blits per frame, while keeping the original command order
intact by flushing pending blits before any fill command.

## Observations

- The accumulator can hold long runs of blit commands when renderers draw many
  sprites or tiles.
- Each `blit` call incurs Python overhead, so grouping them into a single
  `blits` call is a low-risk way to reduce per-frame work.
- Fill commands must preserve ordering relative to blits, so batching is limited
  to consecutive blit segments.

## Implementation notes

- `flush` maintains a pending list of blit tuples in the order they were queued.
- Before processing a fill command, any pending blits are flushed to preserve
  rendering order.
- After the loop, any remaining blits are flushed once.

## Materials

- `src/heart/renderers/internal/frame_accumulator.py`

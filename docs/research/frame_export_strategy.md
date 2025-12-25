# Research Note: Frame export strategy for device presentation

## Problem

`FramePresenter` converts `pygame.Surface` instances into `PIL.Image` payloads
every frame. The fallback path for presenting directly from the display relied
on `pygame.surfarray.array3d` plus NumPy transposition, which allocates arrays
every frame and competes with render time on large displays. We need a single
place to choose the export algorithm so performance-sensitive deployments can
opt into the fastest path without changing code.

## Change Summary

Added a `FrameExporter` helper that centralizes surface-to-image conversion and
selects between a buffer-backed strategy and the existing array strategy. The
default now favors the buffer-backed path, while the array strategy remains
available for environments that prefer explicit array conversion.

## Configuration

- `HEART_FRAME_EXPORT_STRATEGY=buffer` (default) uses `pygame.image.tostring`
  with `Image.frombuffer` for lower per-frame overhead.
- `HEART_FRAME_EXPORT_STRATEGY=array` uses `pygame.surfarray.array3d` with
  axis swapping to match the previous screen export behavior.

## Sources

The prior research on surface export notes that: "Switched to `pygame.image.tostring`
plus `Image.frombuffer` to build the RGBA image directly from SDL's pixel
buffer." (See `docs/research/perf_finalize_rendering.md`.) This informs the new
default because it relies on the same C-backed conversion path.

The array strategy mirrors the frame accumulator work that says:
"`FrameAccumulator.as_array` converts the accumulated surface into an RGB array
by calling `pygame.surfarray.array3d`." (See
`docs/research/frame_accumulator_array_strategy.md`.) This remains available as
an explicit option when that trade-off is desired.

## Materials

- `src/heart/runtime/frame_exporter.py`
- `src/heart/runtime/frame_presenter.py`
- `src/heart/utilities/env/enums.py`
- `src/heart/utilities/env/rendering.py`
- `docs/research/perf_finalize_rendering.md`
- `docs/research/frame_accumulator_array_strategy.md`

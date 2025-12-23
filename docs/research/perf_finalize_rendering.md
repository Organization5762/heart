# Research Note: Faster RGBA extraction in GameLoop

## Context

`GameLoop.__finalize_rendering` in `src/heart/environment.py` converts a
`pygame.Surface` into a `PIL.Image` each frame. The previous approach relied on
`pygame.surfarray` followed by NumPy stacking and transposition, which adds
multiple Python-level array allocations per frame.

## Change Summary

Switched to `pygame.image.tostring` plus `Image.frombuffer` to build the RGBA
image directly from SDL's pixel buffer. This keeps the conversion in C-backed
code paths and avoids extra NumPy copies while keeping the same RGBA output.

## Why This Matters

The conversion runs every render loop iteration. Reducing Python-level array
work lowers per-frame overhead and helps keep frame times stable when multiple
renderers are active.

## Materials

- `src/heart/environment.py` (`GameLoop.__finalize_rendering`)

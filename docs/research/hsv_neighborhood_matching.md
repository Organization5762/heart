# Vectorized HSV neighbourhood matching

## Problem

The HSV-to-BGR conversion in `src/heart/environment.py` includes a neighbourhood
search that corrects float rounding errors. The previous implementation walked
mismatched pixels one at a time and iterated candidate offsets in Python. That
approach added per-pixel overhead in the main render loop, even though the
search itself is purely numeric and well-suited to NumPy broadcasting.

## Approach

The neighbourhood search now builds all candidate BGR offsets for the mismatched
pixels at once, checks bounds, converts candidates back to HSV in a single
NumPy call, and selects the first matching candidate per pixel. This keeps the
calibration logic but moves the heavy work into vectorized operations.

## Materials

- Source: `src/heart/environment.py` (`_convert_hsv_to_bgr`)
- Tests: `tests/test_environment_core_logic.py`

# HSV cache vectorization notes

## Summary

The HSV conversion helpers in `src/heart/environment.py` were spending time looping
pixel-by-pixel to update the shared HSV-to-BGR cache and to re-apply cached
values. That per-element Python overhead shows up during frequent render passes,
so the cache update path was refactored to rely on NumPy unique/value grouping
before touching the ordered dictionary.

## Observations

- `_convert_bgr_to_hsv` previously iterated over every HSV/BGR pair to update
  `HSV_TO_BGR_CACHE`, moving items to the end or inserting new entries one at a
  time.
- `_convert_hsv_to_bgr` looped over every pixel to apply cached values and keep
  the LRU ordering current.
- Most frames reuse a small set of HSV values, so grouping by unique HSV tuples
  allows the cache to be updated with fewer Python-level iterations while
  preserving the LRU ordering based on the last occurrence.

## Implementation notes

- `np.unique(..., axis=0, return_inverse=True)` is used to identify distinct HSV
  values for a frame and provide a stable mapping back to the flattened array.
- Last-occurrence positions are tracked with `np.maximum.at` so that the cache
  can still be ordered by most recent use, matching the previous behaviour.
- Cache application now builds an index map from the unique HSV values to cached
  entries, letting NumPy assign all cached pixels in a single masked write
  instead of repeating `inverse == idx` comparisons for every cached tuple.

## Materials

- `src/heart/environment.py` (`_convert_bgr_to_hsv`, `_convert_hsv_to_bgr`)

______________________________________________________________________

## title: Mandelbrot interior checks for faster convergence

## Problem statement

Rendering the Mandelbrot view in `src/heart/renderers/mandelbrot/scene.py` spends most
of its time iterating points that are mathematically guaranteed to be inside the set.
Skipping those points reduces total iteration work without changing the visible output
for interior regions.

## Observations

The main cardioid and the period-2 bulb are common interior regions that can be tested
analytically before running the escape-time loop. As a reference, Wikipedia describes
the cardioid test as: “A point c is in the main cardioid if it satisfies q(q + (x − 1/4))
≤ 1/4 y², where q = (x − 1/4)² + y².” It also notes: “The period-2 bulb has the equation
(x + 1)² + y² ≤ 1/16.” (Source: <https://en.wikipedia.org/wiki/Mandelbrot_set>).

These checks are directly applicable to `get_mandelbrot_converge_time` and can be
gated behind a configuration flag so the renderer can fall back to the original
algorithm if needed.

## Implementation notes

- Added `MandelbrotInteriorStrategy` and `MandelbrotConfiguration` to make the check
  selectable via `HEART_MANDELBROT_INTERIOR_STRATEGY` (`none` or `cardioid`).
- Implemented `_is_in_mandelbrot_interior` in
  `src/heart/renderers/mandelbrot/scene.py` and used it inside the numba kernel when
  the strategy is enabled.
- Cached Julia render results and palette arrays in the same module to avoid redundant
  allocations on frames with unchanged parameters.

## Materials

- Wikipedia: Mandelbrot set interior tests.
  <https://en.wikipedia.org/wiki/Mandelbrot_set>

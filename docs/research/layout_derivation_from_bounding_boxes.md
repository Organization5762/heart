# Layout derivation from colored bounding boxes

## Problem

We need a way to derive display orientation and layout directly from colored
bounding boxes so the runtime can describe LED positions in 3D space without
hard-coding grid assumptions. The immediate goal is a flat rectangular matrix
representation that can later be replaced with a more flexible projection model.

## Current approach

- Use `ColoredBoundingBox` inputs with 3D bounds and derive axis positions from
  bounding-box centers.
- Compute rows and columns by clustering the centers along each axis.
- Build a perimeter polygon from the min/max XY extents at a reference Z plane.
- Order LED positions by row/column while keeping the underlying 3D centers so
  future projections can ignore the flat-matrix ordering.

Source files:

- `src/heart/derive/layout.py`

## Materials

- None (software-only derivation).

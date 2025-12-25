# Render Surface Helper Refactor

## Problem Statement

The render pipeline in `src/heart/runtime/render_pipeline.py` mixed renderer surface caching, merge strategy selection, and merge execution in the same class. That coupling made it harder to reason about cache behavior versus composition logic and required tests to monkeypatch pipeline methods directly. We need dedicated helpers so the caching and merge behavior are easier to evolve while keeping pipeline-level overrides available for tests.

## Materials

- Local checkout of this repository.
- Python environment with dependencies from `pyproject.toml`.
- Source files in `src/heart/runtime/rendering/` and `src/heart/runtime/render_pipeline.py`.

## Notes

- `RendererSurfaceCache` now owns the per-renderer screen cache used by the runtime pipeline. This keeps the cache keying and screen reset behavior in a focused helper that can be reused or swapped without modifying the pipeline.
- `SurfaceMerger` centralizes merge strategy selection, serial merges, and parallel merge loops. The pipeline still exposes `merge_surfaces` so tests can override the pairwise merge logic, and the helper defers to that callable.
- The render pipeline now wires these helpers into the existing execution flow, keeping the public behavior intact while isolating cache and merge responsibilities.

## References

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/surface_cache.py`
- `src/heart/runtime/rendering/surface_merger.py`
- `tests/test_environment_core_logic.py`

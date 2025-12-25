# Render pipeline composition refactor note

## Problem statement

Document the render pipeline refactor that separates surface preparation, caching, and merge coordination so future contributors can reason about composition responsibilities and extend merge behavior safely.

## Materials

- Local checkout of the Heart repository.
- `src/heart/runtime/render_pipeline.py` for pipeline orchestration changes.
- `src/heart/runtime/rendering/surface_provider.py` for surface preparation and caching.
- `src/heart/runtime/rendering/surface_merge.py` for merge strategy selection and parallel merge coordination.
- `docs/code_flow.md` for the updated runtime flow diagram and narrative.

## Notes

- Surface preparation now lives in a dedicated provider that owns display-mode enforcement and cached surface reuse, keeping `RenderPipeline` focused on orchestration.
- Merge strategy selection and the parallel reduction loop are centralized in the composition manager so serial and parallel rendering share the same strategy controls.
- `RenderPipeline.merge_surfaces` remains as the pairwise merge hook, allowing tests to override the merge function while using the shared composition manager.

## Source references

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/surface_provider.py`
- `src/heart/runtime/rendering/surface_merge.py`
- `docs/code_flow.md`

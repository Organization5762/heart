# Render Pipeline Composition Refactor

## Problem Statement

Describe the responsibilities of the new renderer-processing stage so the runtime pipeline keeps composition logic separate from per-renderer execution and logging.

## Materials

- Local checkout of this repository.
- Python environment with the dependencies listed in `pyproject.toml` installed.
- Source files for the renderer pipeline and rendering utilities.

## Research Notes

- `RendererProcessor` in `src/heart/runtime/rendering/renderer_processor.py` owns surface preparation, renderer initialization, internal processing, and per-renderer timing/logging so the pipeline can focus on orchestration.
- `RenderPipeline` now delegates per-renderer work to `RendererProcessor` while retaining merge-strategy selection, composition, and parallel execution in `src/heart/runtime/render_pipeline.py`.
- The flow diagram in `docs/code_flow.md` now highlights the processor as a distinct service between the pipeline and surface preparation.

## Sources

- `src/heart/runtime/rendering/renderer_processor.py`
- `src/heart/runtime/render_pipeline.py`
- `docs/code_flow.md`

# Render pipeline renderer processor split

## Summary

The renderer-specific surface preparation, initialization, and metrics logging now
live in a dedicated `RendererProcessor` helper. `RenderPipeline` keeps the
render-variant selection and surface composition responsibilities, while
`RendererProcessor` encapsulates per-renderer work so the pipeline reads as a
high-level orchestration step.

## Sources

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/renderer_processor.py`

## Materials

- None

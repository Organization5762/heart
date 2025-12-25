# Render plan centralization note

## Summary

The render planning flow now carries a structured plan object that bundles the chosen renderer variant, merge strategy, and the timing data used for logging. The intent is to keep render selection and logging decisions aligned with a single snapshot of the rendering context.

## Details

- `RenderPlanner.plan` now captures the variant, merge strategy, and timing snapshots together so the logged metadata reflects the exact plan used for the frame.
- `RenderPipeline.render` continues to select the render helper based on the plan, while the helper methods no longer update merge strategy independently.

## Materials

- Source files:
  - `src/heart/runtime/render_planner.py`
  - `src/heart/runtime/render_pipeline.py`

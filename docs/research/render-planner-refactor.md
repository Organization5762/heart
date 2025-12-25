# Render planner refactor notes

## Problem

The render pipeline mixed render strategy selection, logging, and surface composition in one class, which made it harder to track the decision logic separately from frame assembly.

## Approach

Extracted render planning responsibilities into a dedicated planner object so the pipeline focuses on orchestrating renderers and composing surfaces while the planner handles strategy selection and logging.

## Materials

- `src/heart/runtime/render_pipeline.py`
- `src/heart/runtime/rendering/planner.py`
- `src/heart/runtime/rendering/timing.py`

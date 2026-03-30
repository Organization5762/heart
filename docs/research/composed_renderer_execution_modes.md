# Composed renderer execution modes

## Problem Statement

`ComposedRenderer` previously flattened its child renderers into the outer render list, which meant the composed node did not own execution. That prevented the renderer layer from expressing serial barriers or parallel child groups as part of the navigation tree.

## Materials

- `src/heart/navigation/composed_renderer.py`
- `src/heart/navigation/renderer_specs.py`
- `src/heart/runtime/rendering/renderer_processor.py`
- `src/heart/runtime/rendering/surface/collection.py`
- `src/heart/runtime/rendering/surface/merge.py`
- `tests/navigation/test_composed_renderer_execution.py`

## Notes

`ComposedRenderer` now acts as a real execution node. Its `get_renderers()` path returns the composed node itself, and its `real_process()` method is responsible for running child renderers, collecting child surfaces, and merging those surfaces back into a single frame.

Execution mode is explicit through `ComposedRendererExecutionMode`:

- `SERIAL` renders children in list order on the calling thread.
- `PARALLEL` uses the existing threaded surface collector to render children concurrently and then merges the resulting surfaces in the original list order.

This keeps layering deterministic even when child completion order differs. The graph model is a nested tree of composed nodes rather than a general DAG, which is enough to express serial barriers and parallel groups without introducing a second composition API.

Parallel execution is guarded at the renderer level through `can_render_in_parallel()`. The default guard rejects `OPENGL` renderers, and any composed node in parallel mode falls back to serial execution for the full group when one or more children report that they are unsafe to render concurrently.

## Validation

- `pytest tests/navigation/test_composed_renderer_resolution.py tests/navigation/test_composed_renderer_execution.py tests/navigation/test_multi_scene_resolution.py tests/runtime/test_container.py -q`

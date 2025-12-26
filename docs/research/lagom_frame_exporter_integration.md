# Lagom Frame Exporter Integration Note

## Problem Statement

`FramePresenter` constructed its own `FrameExporter` instance, which made it
hard to override export strategies through the Lagom container for tests or
runtime tuning. That kept frame export behavior outside the shared dependency
wiring and forced direct constructor access when configuring exporters.

## Materials

- Python 3.11 environment with `uv` for dependency resolution.
- Lagom dependency (`lagom` in `pyproject.toml`).
- Source modules: `src/heart/runtime/container.py`,
  `src/heart/runtime/frame_presenter.py`,
  `src/heart/runtime/frame_exporter.py`.
- Tests: `tests/runtime/test_container.py`.

## Notes

- Registered `FrameExporter` as a Lagom singleton in
  `heart.runtime.container.configure_runtime_container`.
- `FramePresenter` now accepts the exporter through the container so overrides
  can swap export strategies without bypassing runtime wiring.
- Added a container test to confirm that overriding `FrameExporter` updates the
  `FramePresenter` instance resolved from the container.

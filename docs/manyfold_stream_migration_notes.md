# Manyfold Stream Migration Notes

This note records the cleanup completed after removing the old RX-oriented
Heart utility layer.

## Current Direction

- Heart code should expose `manyfold.StreamNode` or graph route handles at public
  boundaries.
- Callback-backed bridges should use `manyfold.CallbackObservable` or
  `manyfold.stream_from`.
- Push-style test and input sources should use
  `manyfold.EventStream`.
- Peripheral lifecycle cleanup should use the graph/runtime shutdown primitive
  already exported by `manyfold`.

## Validation Targets

Run these checks when touching this area:

```bash
rg -n "heart\\.utilities\\.<old-backend>|from <old-backend>|<old-backend>" src tests scripts pyproject.toml
pytest tests/peripheral/test_event_streams.py tests/peripheral/test_input_core.py tests/peripheral/test_switch.py
```

The lockfile may still contain the backend package while the pinned Manyfold
build declares it transitively. Heart should not depend on it directly.

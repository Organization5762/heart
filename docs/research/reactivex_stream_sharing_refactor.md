# Reactivex stream sharing refactor notes

## Problem statement

The reactive stream sharing logic previously lived in a single module that mixed
configuration loading, sharing strategies, and stream instrumentation. This
made it harder to locate the right concerns when updating operators or reading
how settings were applied.

## Materials

- Source files:
  - `src/heart/utilities/reactivex/stream_config.py`
  - `src/heart/utilities/reactivex/stream_ops.py`
  - `src/heart/utilities/reactivex/stream_sharing.py`
  - `src/heart/utilities/reactivex_streams.py`
- Dependency: `reactivex`

## Notes

- Configuration gathering now lives in `StreamShareSettings` to keep the
  environment lookups together.
- Stream operators such as coalescing, instrumentation, and refcount grace
  handling are grouped in `stream_ops.py` to separate them from strategy
  selection.
- `share_stream` remains the single entry point for strategy selection, with a
  small compatibility wrapper in `reactivex_streams.py` for existing imports.

## References

- Stream sharing entry point: `src/heart/utilities/reactivex/stream_sharing.py`.
- Stream operators and schedulers: `src/heart/utilities/reactivex/stream_ops.py`.
- Environment settings: `src/heart/utilities/reactivex/stream_config.py`.

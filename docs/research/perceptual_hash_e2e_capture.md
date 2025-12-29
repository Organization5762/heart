<!-- markdownlint-disable MD013 -->

# Perceptual hash coverage for ScreenRecorder outputs

## Context

ScreenRecorder writes GIFs that are used to validate end-to-end rendering. The current tests perform exact pixel comparisons, which are brittle when renderer behavior shifts or encoding details change. The request is to introduce perceptual hashing so the suite can tolerate larger visual changes while still detecting meaningful regressions.

## Goal

Add a perceptual-hash based test that verifies ScreenRecorder output stays visually consistent with a known baseline for a small deterministic scene. Use `imagehash` so the comparison is resilient to pixel-level variations while still flagging major departures.

## Materials

- Software: `imagehash`, `Pillow`, `pytest`
- Code: `src/heart/display/recorder.py`, `tests/display/test_screen_recorder.py`

## Notes

- The test lives in `tests/display/test_screen_recorder.py` alongside the existing ScreenRecorder coverage.
- A synthetic pattern is drawn via a renderer to avoid dependency on external assets.
- The expected frame is constructed with `PIL.Image` and hashed with `imagehash.phash` to keep the baseline deterministic.
- The hash distance threshold is small (`<= 2`) to catch visual drift without making the test overly brittle.

## References

- `src/heart/display/recorder.py`
- `tests/display/test_screen_recorder.py`

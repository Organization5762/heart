# Runtime observability additions

## Problem statement

Record how recent runtime updates expose LED frame output and Mario state changes as observables so downstream components can subscribe without scraping internal state.

## Materials

- Local checkout of this repository.
- Python environment with dependencies from `pyproject.toml`.

## Notes

- LED frame emission now uses the `LEDMatrixDisplay` peripheral to publish `DisplayFrame` payloads whenever the run loop outputs an image. The capture happens inside `GameLoop._one_loop` and is registered with the `PeripheralManager` so observers can subscribe through the event bus (`src/heart/environment.py`, `src/heart/peripheral/led_matrix.py`).
- Mario animation updates are now driven by the game tick clock, and state transitions are shared through a cached observable so other components can attach without duplicating subscriptions (`src/heart/renderers/mario/provider.py`, `src/heart/renderers/mario/state.py`).
- CLI orientation selection now allows non-cube layouts by mapping `--orientation` and layout dimensions into a concrete `Orientation` before the device is created (`src/heart/loop.py`).

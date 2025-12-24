# Runtime Observability Research Note

## Problem Statement

Runtime consumers need direct access to rendered output and renderer state updates so that
analytics, companion effects, and diagnostics can subscribe to live signals without
instrumenting the core render loop.

## Materials

- Local Heart repository checkout.
- Python environment capable of running the Heart runtime.
- Access to the runtime sources under `src/heart/`.

## Sources Consulted

- `src/heart/peripheral/led_matrix.py` for the display-frame peripheral interface.
- `src/heart/environment.py` for GameLoop frame publishing hooks.
- `src/heart/renderers/mario/provider.py` for state stream construction.
- `src/heart/loop.py` for CLI-driven runtime configuration.

## Findings

- Registering `LEDMatrixDisplay` with the `PeripheralManager` makes rendered frames observable
  through the same event bus used by physical peripherals.
- The Mario renderer provider can expose a shared `MarioRendererState` observable so other
  components can subscribe to animation timing and acceleration-triggered transitions.
- Publishing frame metadata alongside the image payload provides enough context for consumers
  to identify active renderers without tight coupling to the renderer pipeline.

## Follow-Up Ideas

- Emit renderer state updates for additional interactive renderers that benefit from external
  diagnostics or synchronization.
- Add a lightweight sampling hook that downscales frames before emitting them to reduce
  downstream bandwidth when needed.
